#!/usr/bin/env python3
"""Assemble weekly Telegram digest from _build/{date}/ JSON chunks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import get_inbox_dir, project_root

BUILD_DIRNAME = "_build"
SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
URL_ONLY = re.compile(
    r"^\s*(https?://\S+|\[.*?\]\(https?://[^)]+\))\s*$",
    re.IGNORECASE,
)


def _require_str(obj: dict[str, Any], key: str, path: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: missing or empty '{key}'")
    return value.strip()


def _sentence_count(text: str) -> int:
    parts = [p.strip() for p in SENTENCE_SPLIT.split(text.strip()) if p.strip()]
    return max(len(parts), 1 if text.strip() else 0)


def _normalize_for_compare(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def validate_full_topic(topic: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    for key in ("teaser", "url", "problem", "context", "solution"):
        value = topic.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}: missing or empty '{key}'")

    if errors:
        return errors

    teaser = topic["teaser"].strip()
    context = topic["context"].strip()
    solution = topic["solution"].strip()

    context_ok = _sentence_count(context) >= 2 or len(context) >= 200
    if not context_ok:
        errors.append(
            f"{path}: context too thin "
            f"(sentences={_sentence_count(context)}, chars={len(context)}; "
            "need ≥2 sentences or ≥200 chars)"
        )

    solution_ok = _sentence_count(solution) >= 1 or len(solution) >= 80
    if not solution_ok:
        errors.append(
            f"{path}: solution too thin "
            f"(sentences={_sentence_count(solution)}, chars={len(solution)}; "
            "need ≥1 sentence or ≥80 chars)"
        )

    if _normalize_for_compare(context) == _normalize_for_compare(teaser):
        errors.append(f"{path}: context must not equal teaser")

    if URL_ONLY.match(context):
        errors.append(f"{path}: context must not be link-only")

    return errors


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_build_dir(date: str) -> Path:
    build_dir = project_root() / BUILD_DIRNAME / date
    if not build_dir.is_dir():
        raise SystemExit(f"Build directory not found: {build_dir}")
    return build_dir


def load_meta(build_dir: Path) -> dict[str, Any]:
    meta_path = build_dir / "meta.json"
    if not meta_path.exists():
        raise SystemExit(f"Missing {meta_path}")
    meta = load_json(meta_path)
    if not isinstance(meta, dict):
        raise SystemExit(f"{meta_path}: expected object")
    return meta


def load_channel_file(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if isinstance(data, dict) and isinstance(data.get("channels"), list):
        return data["channels"]
    if isinstance(data, list):
        return data
    raise SystemExit(f"{path}: expected object with 'channels' or a list")


def validate_channel_topics(
    channels: list[dict[str, Any]],
    *,
    source: str,
    alumni: bool,
) -> list[str]:
    errors: list[str] = []
    for ci, channel in enumerate(channels):
        name = channel.get("name") or channel.get("channel") or f"channel[{ci}]"
        base = f"{source}/{name}"
        topics = channel.get("topics") or []
        if not isinstance(topics, list):
            errors.append(f"{base}: 'topics' must be a list")
            continue
        if len(topics) > 5 and not alumni:
            errors.append(f"{base}: more than 5 full topics ({len(topics)})")
        for ti, topic in enumerate(topics):
            if not isinstance(topic, dict):
                errors.append(f"{base}/topics[{ti}]: expected object")
                continue
            topic_id = topic.get("theme") or topic.get("teaser") or f"topic[{ti}]"
            path = f"{base}/topics[{ti}:{topic_id}]"
            if alumni and not (topic.get("theme") or topic.get("teaser")):
                errors.append(f"{path}: alumni topic needs 'theme' or 'teaser'")
            errors.extend(validate_full_topic(topic, path))

        more = channel.get("more_topics") or []
        if not isinstance(more, list):
            errors.append(f"{base}: 'more_topics' must be a list")
        elif len(more) > 10:
            errors.append(f"{base}: more than 10 more_topics ({len(more)})")
        elif not alumni:
            for mi, item in enumerate(more):
                if not isinstance(item, dict):
                    errors.append(f"{base}/more_topics[{mi}]: expected object")
                    continue
                if not str(item.get("summary") or "").strip():
                    errors.append(f"{base}/more_topics[{mi}]: missing 'summary'")
                if not str(item.get("url") or "").strip():
                    errors.append(f"{base}/more_topics[{mi}]: missing 'url'")
        else:
            for mi, item in enumerate(more):
                if not isinstance(item, dict):
                    errors.append(f"{base}/more_topics[{mi}]: expected object")
                    continue
                if not str(item.get("theme") or "").strip():
                    errors.append(f"{base}/more_topics[{mi}]: missing 'theme'")
                if not str(item.get("url") or "").strip():
                    errors.append(f"{base}/more_topics[{mi}]: missing 'url'")

        omitted = channel.get("omitted_count", 0)
        if omitted is not None and (
            not isinstance(omitted, int) or omitted < 0
        ):
            errors.append(f"{base}: 'omitted_count' must be a non-negative int")
    return errors


def render_full_topic(topic: dict[str, Any], display_name: str) -> str:
    teaser = topic["teaser"].strip()
    url = topic["url"].strip()
    problem = topic["problem"].strip()
    context = topic["context"].strip()
    solution = topic["solution"].strip()
    return "\n".join(
        [
            f"**{display_name}** — [пост]({url}): {teaser}",
            "- [ ] Почитать в телеграмме",
            "",
            "> [!abstract]- Подробнее",
            f"> **Проблема:** {problem}",
            ">",
            f"> **Контекст:** {context}",
            ">",
            f"> **Решение:** {solution}",
            ">",
            "> - [ ] Полезно",
            ">",
            f"> → [Читать в Telegram]({url})",
            "",
        ]
    )


def render_channel_section(channel: dict[str, Any], *, alumni: bool) -> str:
    name = str(channel.get("name") or channel.get("channel") or "Канал").strip()
    short = str(channel.get("short_name") or name).strip()
    lines: list[str] = [f"### {name}", ""]

    for topic in channel.get("topics") or []:
        display = short
        if alumni and topic.get("theme"):
            display = short
        lines.append(render_full_topic(topic, display))

    more = channel.get("more_topics") or []
    omitted = int(channel.get("omitted_count") or 0)
    if more:
        if alumni:
            lines.append("### Ещё темы Alumni")
            lines.append("")
            for item in more:
                theme = str(item.get("theme") or "").strip()
                url = str(item.get("url") or "").strip()
                count = item.get("post_count")
                count_part = f" ({count} поста)" if count else ""
                if count == 1:
                    count_part = " (1 пост)"
                elif isinstance(count, int) and count >= 2 and count <= 4:
                    count_part = f" ({count} поста)"
                elif isinstance(count, int) and count:
                    count_part = f" ({count} постов)"
                lines.append(f"- {theme}{count_part} — [пост]({url})")
            lines.append("")
            if omitted > 0:
                lines.append(
                    f"_Есть ещё {omitted} мелких тем, не вошедших в список._"
                )
                lines.append("")
        else:
            lines.append("### Ещё темы")
            lines.append("")
            for item in more:
                summary = str(item.get("summary") or "").strip()
                url = str(item.get("url") or "").strip()
                lines.append(f"- {summary} — [пост]({url})")
            lines.append("")
            if omitted > 0:
                lines.append(f"_Ещё {omitted} не вошло в подборку._")
                lines.append("")
    elif omitted > 0 and not alumni:
        lines.append(f"_Ещё {omitted} не вошло в подборку._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n\n"


def render_digest(
    *,
    date: str,
    meta: dict[str, Any],
    alumni_channels: list[dict[str, Any]],
    tier2_channels: list[dict[str, Any]],
    other_channels: list[dict[str, Any]],
) -> str:
    parts: list[str] = [
        "---",
        f"created_at: {meta.get('created_at', '')}",
        f"period_from: {meta.get('period_from', '')}",
        f"period_to: {meta.get('period_to', '')}",
        "source: telegram-inbox",
        f"export_run_id: {meta.get('export_run_id', '')}",
        f"export_status: {meta.get('export_status', '')}",
        "---",
        "",
        f"# Telegram Digest {date}",
        "",
        "## Страница 1 · Captain Alumni",
        "",
    ]

    for channel in alumni_channels:
        parts.append(render_channel_section(channel, alumni=True))

    parts.append("<!-- page-break -->")
    parts.append("")

    for channel in tier2_channels:
        parts.append(render_channel_section(channel, alumni=False))

    if tier2_channels:
        parts.append("<!-- page-break -->")
        parts.append("")

    if other_channels:
        parts.append("## Страница 3 · Каналы 2weeks")
        parts.append("")
        for channel in other_channels:
            parts.append(render_channel_section(channel, alumni=False))

    inactive = meta.get("inactive_channels") or []
    if inactive:
        parts.append("## Каналы без активности")
        parts.append("")
        parts.append(", ".join(str(x) for x in inactive))
        parts.append("")

    failed = meta.get("failed_channels") or []
    if failed or meta.get("export_status") == "complete_with_errors":
        parts.append("## Экспорт неполный")
        parts.append("")
        if failed:
            labels = []
            for item in failed:
                if isinstance(item, dict):
                    labels.append(str(item.get("ref") or item.get("name") or item))
                else:
                    labels.append(str(item))
            parts.append(
                "Не удалось экспортировать: "
                + ", ".join(labels)
                + ". Дайджест может не включать эти каналы."
            )
        else:
            parts.append(
                "Экспорт завершился с ошибками. Дайджест может быть неполным."
            )
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def assemble(
    date: str,
    *,
    write: bool = True,
    inbox_dir: Path | None = None,
    build_root: Path | None = None,
) -> Path | None:
    if build_root is not None:
        build_dir = Path(build_root) / date
        if not build_dir.is_dir():
            raise SystemExit(f"Build directory not found: {build_dir}")
    else:
        build_dir = resolve_build_dir(date)
    meta = load_meta(build_dir)

    alumni_path = build_dir / "alumni.json"
    tier2_path = build_dir / "tier_2.json"
    if not alumni_path.exists():
        raise SystemExit(f"Missing {alumni_path}")
    if not tier2_path.exists():
        raise SystemExit(f"Missing {tier2_path}")

    alumni_channels = load_channel_file(alumni_path)
    tier2_channels = load_channel_file(tier2_path)

    batch_names = meta.get("other_batches")
    if batch_names is None:
        batch_names = sorted(
            p.name for p in build_dir.glob("other_batch_*.json")
        )
    if not isinstance(batch_names, list):
        raise SystemExit("meta.json: 'other_batches' must be a list of filenames")

    other_channels: list[dict[str, Any]] = []
    errors: list[str] = []

    errors.extend(
        validate_channel_topics(alumni_channels, source="alumni.json", alumni=True)
    )
    errors.extend(
        validate_channel_topics(tier2_channels, source="tier_2.json", alumni=False)
    )

    for batch_name in batch_names:
        batch_path = build_dir / str(batch_name)
        if not batch_path.exists():
            errors.append(f"missing batch file listed in meta: {batch_name}")
            continue
        channels = load_channel_file(batch_path)
        errors.extend(
            validate_channel_topics(
                channels, source=str(batch_name), alumni=False
            )
        )
        other_channels.extend(channels)

    if errors:
        print("Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        raise SystemExit(1)

    markdown = render_digest(
        date=date,
        meta=meta,
        alumni_channels=alumni_channels,
        tier2_channels=tier2_channels,
        other_channels=other_channels,
    )

    if not write:
        print("Validation OK (dry-run, no file written)")
        return None

    inbox = Path(inbox_dir) if inbox_dir is not None else get_inbox_dir()
    out_dir = inbox / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"Telegram Digest {date}.md"
    out_path.write_text(markdown, encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble Telegram Digest from _build/{date}/ JSON chunks."
    )
    parser.add_argument(
        "date",
        help="Digest date folder under _build/, e.g. 18_07_2026",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only; do not write the final digest file",
    )
    parser.add_argument(
        "--inbox-dir",
        type=Path,
        default=None,
        help="Override INBOX_DIR for output (tests / local overrides)",
    )
    args = parser.parse_args()
    assemble(args.date, write=not args.dry_run, inbox_dir=args.inbox_dir)


if __name__ == "__main__":
    main()
