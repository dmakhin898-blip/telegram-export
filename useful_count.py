"""Lifetime «Полезно» counts and within-tier channel order."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

TME_C = re.compile(r"https?://t\.me/c/(\d+)/(\d+)", re.IGNORECASE)
TME_USER = re.compile(
    r"https?://t\.me/([A-Za-z][A-Za-z0-9_]*)/(\d+)",
    re.IGNORECASE,
)
EXPORT_HEADING = re.compile(
    r"^## [^|]+ \| .+ \(([^)]+)\) \| msg:(\d+)\s*$"
)
TEASER = re.compile(
    r"^\*\*.+\*\*\s+—\s+\[пост\]\((https?://[^)\s]+)\)"
)
USEFUL_BOX = re.compile(
    r"^\s*(?:>\s*)*-\s+\[([ xX])\]\s+Полезно\s*$"
)
FILENAME_DATE = re.compile(r"(\d{2})_(\d{2})_(\d{4})")


class _ExportIndex:
    """Export headings `slug (id) | msg:{n}` and usernames taught from them."""

    def __init__(self) -> None:
        self._ids_for_msg: dict[int, set[str]] = {}
        self._msgs_for_id: dict[str, set[int]] = {}
        self._taught: dict[str, str] = {}

    def add_heading(self, channel_id: str, message_id: int) -> None:
        self._ids_for_msg.setdefault(message_id, set()).add(channel_id)
        self._msgs_for_id.setdefault(channel_id, set()).add(message_id)

    def resolve(self, url: str, *, teach: bool) -> str | None:
        private = TME_C.search(url)
        if private is not None:
            channel_id = private.group(1)
            if channel_id in self._msgs_for_id:
                return channel_id
            return None

        public = TME_USER.search(url)
        if public is None:
            return None
        username = public.group(1).lower()
        message_id = int(public.group(2))
        channel_ids = self._ids_for_msg.get(message_id, ())
        if len(channel_ids) == 1:
            found = next(iter(channel_ids))
            if teach:
                self._taught.setdefault(username, found)
            return found
        taught = self._taught.get(username)
        if taught is not None:
            return taught
        return None


class UsefulCount:
    """Map of export channel id → lifetime useful marks. A missing id is 0."""

    def __init__(self, counts: dict[str, int], index: _ExportIndex) -> None:
        self._counts = counts
        self._index = index

    def __getitem__(self, channel_id: object) -> int:
        return self._counts.get(str(channel_id), 0)

    def section_id(self, channel: dict[str, Any]) -> str | None:
        """Export id shared by the channel's full-topic URLs.

        Mixed ids have no single section id. URLs that do not resolve are
        ignored. Zero resolved URLs also have no section id.
        """
        resolved: list[str] = []
        for url in _topic_urls(channel):
            channel_id = self._index.resolve(url, teach=False)
            if channel_id is not None:
                resolved.append(channel_id)
        unique = set(resolved)
        if len(unique) != 1:
            return None
        return next(iter(unique))

    def section_count(self, channel: dict[str, Any]) -> int:
        channel_id = self.section_id(channel)
        if channel_id is None:
            return 0
        return self[channel_id]


def load_useful_counts(
    inbox_dir: Path | str,
    *,
    exclude: Path | str | None = None,
) -> UsefulCount:
    """Count checked «Полезно» boxes in `{inbox}/digests`, skipping `exclude`.

    Dated files are read from the oldest `dd_mm_yyyy` in the filename to the
    newest. A markdown file with no such date is read after every dated file.
    """
    inbox = Path(inbox_dir)
    index = _read_export_index(inbox)
    counts: dict[str, int] = {}
    exclude_path = Path(exclude).resolve() if exclude is not None else None
    for path in _digest_files(inbox):
        if exclude_path is not None and path.resolve() == exclude_path:
            continue
        _count_file(path, index, counts)
    return UsefulCount(counts, index)


def order_sections(
    channels: list[dict[str, Any]],
    useful: UsefulCount,
    tie_refs: Sequence[object],
) -> list[dict[str, Any]]:
    """Annotate `useful_count` and return channels highest count first.

    Equal counts keep `tie_refs` order (the tier's `channels.yaml` list).
    Channels missing from that list keep their incoming relative order
    after every listed channel.
    """
    ranked: list[tuple[int, int, int, dict[str, Any]]] = []
    for index, channel in enumerate(channels):
        section_id = useful.section_id(channel)
        count = 0 if section_id is None else useful[section_id]
        channel["useful_count"] = count
        rank = _tie_rank(channel, section_id, tie_refs)
        ranked.append((-count, rank, index, channel))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in ranked]


def _read_export_index(inbox: Path) -> _ExportIndex:
    index = _ExportIndex()
    if not inbox.is_dir():
        return index
    for path in sorted(inbox.rglob("*.md")):
        if not path.is_file():
            continue
        if _is_under_digests(inbox, path):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = EXPORT_HEADING.match(line)
            if match is None:
                continue
            index.add_heading(match.group(1), int(match.group(2)))
    return index


def _digest_files(inbox: Path) -> list[Path]:
    digests = inbox / "digests"
    if not digests.is_dir():
        return []
    files = [path for path in digests.rglob("*.md") if path.is_file()]
    return sorted(files, key=_digest_file_order)


def _digest_file_order(path: Path) -> tuple[int, date, str, str]:
    parsed = _date_in_filename(path.name)
    if parsed is None:
        return (1, date.max, path.name, path.as_posix())
    return (0, parsed, path.name, path.as_posix())


def _date_in_filename(name: str) -> date | None:
    match = FILENAME_DATE.search(name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(0), "%d_%m_%Y").date()
    except ValueError:
        return None


def _is_under_digests(inbox: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(inbox.resolve())
    except ValueError:
        return False
    return bool(relative.parts) and relative.parts[0] == "digests"


def _count_file(path: Path, index: _ExportIndex, counts: dict[str, int]) -> None:
    text = path.read_text(encoding="utf-8")
    for section in _channel_sections(text):
        parsed: list[tuple[bool, str | None]] = []
        for url, checked in _full_topics(section):
            parsed.append((checked, index.resolve(url, teach=True)))
        ids = {channel_id for _, channel_id in parsed if channel_id is not None}
        if len(ids) != 1:
            continue
        section_id = next(iter(ids))
        for checked, channel_id in parsed:
            if checked and channel_id == section_id:
                counts[section_id] = counts.get(section_id, 0) + 1


def _channel_sections(text: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("### ") and not line.startswith("### Ещё темы"):
            if in_section:
                sections.append("\n".join(current))
            current = [line]
            in_section = True
            continue
        if in_section:
            current.append(line)
    if in_section:
        sections.append("\n".join(current))
    return sections


def _full_topics(section: str) -> list[tuple[str, bool]]:
    topics: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in section.splitlines():
        teaser = TEASER.match(line)
        if teaser is not None:
            current = {"url": teaser.group(1), "checked": False}
            topics.append(current)
            continue
        box = USEFUL_BOX.match(line)
        if box is not None and current is not None and box.group(1).lower() == "x":
            current["checked"] = True
    return [(str(topic["url"]), bool(topic["checked"])) for topic in topics]


def _topic_urls(channel: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    topics = channel.get("topics") or []
    if not isinstance(topics, list):
        return urls
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        url = topic.get("url")
        if isinstance(url, str) and url.strip():
            urls.append(url.strip())
    return urls


def _tie_rank(
    channel: dict[str, Any],
    section_id: str | None,
    tie_refs: Sequence[object],
) -> int:
    usernames = {
        username
        for url in _topic_urls(channel)
        if (username := _username_in_url(url)) is not None
    }
    normalized_section = _bare_channel_id(section_id) if section_id is not None else None
    for index, ref in enumerate(tie_refs):
        bare = _bare_channel_id(ref)
        if (
            normalized_section is not None
            and bare is not None
            and bare == normalized_section
        ):
            return index
        username = _username_in_ref(ref)
        if username is not None and username in usernames:
            return index
    return len(tie_refs)


def _username_in_url(url: str) -> str | None:
    if TME_C.search(url):
        return None
    match = TME_USER.search(url)
    if match is None:
        return None
    return match.group(1).lower()


def _username_in_ref(ref: object) -> str | None:
    if not isinstance(ref, str):
        return None
    text = ref.strip().strip('"').strip("'")
    if not text.startswith("@"):
        return None
    name = text[1:].strip()
    if not name:
        return None
    return name.lower()


def _bare_channel_id(ref: object) -> str | None:
    if isinstance(ref, bool):
        return None
    if isinstance(ref, int):
        text = str(ref)
    elif isinstance(ref, str):
        text = ref.strip().strip('"').strip("'")
    else:
        return None
    if text.startswith("-100") and text[4:].isdigit():
        return text[4:]
    if text.isdigit():
        return text
    return None
