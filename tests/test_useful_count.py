#!/usr/bin/env python3
"""Fixture tests for lifetime useful counts and within-tier order."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from useful_count import load_useful_counts, order_sections  # noqa: E402


def _export_heading(
    slug: str,
    channel_id: str,
    message_id: int,
    username: str | None = None,
) -> str:
    if username:
        key = f"{slug} (@{username}) ({channel_id})"
    else:
        key = f"{slug} ({channel_id})"
    return (
        f"## 2026-01-01 00:00:00 UTC | {key} | msg:{message_id}\n\n"
        "post\n\n---\n"
    )


def _topic(url: str, *, checked: bool) -> str:
    mark = "x" if checked else " "
    return "\n".join(
        [
            f"**Channel** — [пост]({url}): Синтез темы в одном предложении.",
            "- [ ] Почитать в телеграмме",
            "",
            "> [!abstract]- Подробнее",
            "> **Проблема:** пример",
            ">",
            "> **Контекст:** пример контекста без отметки в прозе.",
            ">",
            "> **Решение:** пример решения.",
            ">",
            f"> - [{mark}] Полезно",
            ">",
            f"> → [Читать в Telegram]({url})",
            "",
        ]
    )


def _section(title: str, body: str) -> str:
    return f"### {title}\n\n{body}"


def _write_shared_post_export(inbox: Path) -> None:
    """Msg 50 is in two channels. Msg 77 belongs only to channel 111."""
    export = inbox / "channels" / "2026-01.md"
    export.parent.mkdir(parents=True)
    export.write_text(
        _export_heading("alpha", "111", 50)
        + _export_heading("beta", "222", 50)
        + _export_heading("alpha", "111", 77),
        encoding="utf-8",
    )


class UsefulCountTests(unittest.TestCase):
    def test_username_and_private_link_share_one_count_when_titles_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            export = inbox / "dark-side" / "2026-01.md"
            export.parent.mkdir(parents=True)
            export.write_text(
                _export_heading("dark-side", "555", 10)
                + _export_heading("dark-side", "555", 11),
                encoding="utf-8",
            )
            digests = inbox / "digests"
            digests.mkdir()
            (digests / "Telegram Digest 01_01_2098.md").write_text(
                _section(
                    "Тёмная сторона",
                    _topic("https://t.me/darkside/10", checked=True),
                ),
                encoding="utf-8",
            )
            (digests / "Telegram Digest 08_01_2098.md").write_text(
                _section(
                    "Тёмная сторона / Темнографика",
                    _topic("https://t.me/c/555/11", checked=True)
                    + _topic("https://t.me/c/555/4040", checked=True)
                    + _topic("https://t.me/missing_user/999", checked=True),
                ),
                encoding="utf-8",
            )

            counts = load_useful_counts(inbox)
            self.assertEqual(counts["555"], 3)
            self.assertEqual(counts["999"], 0)

    def test_unchecked_read_checkbox_and_prose_do_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            export = inbox / "example-author" / "2026-01.md"
            export.parent.mkdir(parents=True)
            export.write_text(
                _export_heading("example-author", "2222222222", 10),
                encoding="utf-8",
            )
            digests = inbox / "digests"
            digests.mkdir()
            prose = "\n".join(
                [
                    "**Channel** — [пост](https://t.me/example_author/10): Это Полезно знать.",
                    "- [x] Почитать в телеграмме",
                    "",
                    "> [!abstract]- Подробнее",
                    "> **Контекст:** слово Полезно встречается в прозе и не является галкой.",
                    ">",
                    "> - [ ] Полезно",
                    ">",
                    "> → [Читать в Telegram](https://t.me/example_author/10)",
                    "",
                ]
            )
            (digests / "Telegram Digest 01_01_2098.md").write_text(
                _section("Example Author", prose),
                encoding="utf-8",
            )

            counts = load_useful_counts(inbox)
            self.assertEqual(counts["2222222222"], 0)

    def test_excluded_file_and_yaml_tie_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            export = inbox / "channels" / "2026-01.md"
            export.parent.mkdir(parents=True)
            headings = [
                _export_heading("high", "11", message_id) for message_id in range(101, 110)
            ]
            headings.append(_export_heading("zero-a", "21", 201))
            headings.append(_export_heading("zero-b", "22", 202))
            export.write_text("".join(headings), encoding="utf-8")

            digests = inbox / "digests"
            digests.mkdir()
            kept = digests / "Telegram Digest 01_01_2098.md"
            dropped = digests / "Telegram Digest 02_01_2098.md"
            kept_topics = "".join(
                _topic(f"https://t.me/high/{message_id}", checked=True)
                for message_id in range(101, 105)
            )
            kept.write_text(_section("High old", kept_topics), encoding="utf-8")
            dropped_topics = "".join(
                _topic(f"https://t.me/high/{message_id}", checked=True)
                for message_id in range(101, 110)
            )
            dropped.write_text(_section("High replaced", dropped_topics), encoding="utf-8")

            counts = load_useful_counts(inbox, exclude=dropped)
            self.assertEqual(counts["11"], 4)

            channels = [
                {
                    "name": "Zero B",
                    "topics": [{"url": "https://t.me/zero_b/202"}],
                },
                {
                    "name": "High",
                    "topics": [{"url": "https://t.me/high/101"}],
                },
                {
                    "name": "Zero A",
                    "topics": [{"url": "https://t.me/zero_a/201"}],
                },
            ]
            ordered = order_sections(
                channels,
                counts,
                ["@zero_a", "@zero_b", "@high"],
            )
            self.assertEqual(
                [channel["name"] for channel in ordered],
                ["High", "Zero A", "Zero B"],
            )
            self.assertEqual(
                [channel["useful_count"] for channel in ordered],
                [4, 0, 0],
            )

    def test_mixed_section_ids_add_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            export = inbox / "channels" / "2026-01.md"
            export.parent.mkdir(parents=True)
            export.write_text(
                _export_heading("one", "111", 1) + _export_heading("two", "222", 1),
                encoding="utf-8",
            )
            digests = inbox / "digests"
            digests.mkdir()
            body = _topic("https://t.me/c/111/1", checked=True) + _topic(
                "https://t.me/c/222/1", checked=True
            )
            (digests / "Telegram Digest 01_01_2098.md").write_text(
                _section("Mixed", body),
                encoding="utf-8",
            )

            counts = load_useful_counts(inbox)
            self.assertEqual(counts["111"], 0)
            self.assertEqual(counts["222"], 0)

    def test_later_filename_does_not_open_earlier_ambiguous_mark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            _write_shared_post_export(inbox)
            digests = inbox / "digests"
            digests.mkdir()
            (digests / "Telegram Digest 21_06_2026.md").write_text(
                _section(
                    "June",
                    _topic("https://t.me/sharedname/50", checked=True),
                ),
                encoding="utf-8",
            )
            (digests / "Telegram Digest 20_09_2026.md").write_text(
                _section(
                    "September",
                    _topic("https://t.me/sharedname/77", checked=True),
                ),
                encoding="utf-8",
            )

            counts = load_useful_counts(inbox)
            self.assertEqual(counts["111"], 1)
            self.assertEqual(counts["222"], 0)

    def test_older_file_teaches_name_so_newer_ambiguous_mark_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            _write_shared_post_export(inbox)
            digests = inbox / "digests"
            digests.mkdir()
            (digests / "Telegram Digest 21_06_2026.md").write_text(
                _section(
                    "June",
                    _topic("https://t.me/sharedname/77", checked=False),
                ),
                encoding="utf-8",
            )
            (digests / "Telegram Digest 20_09_2026.md").write_text(
                _section(
                    "September",
                    _topic("https://t.me/sharedname/50", checked=True),
                ),
                encoding="utf-8",
            )

            counts = load_useful_counts(inbox)
            self.assertEqual(counts["111"], 1)
            self.assertEqual(counts["222"], 0)

    def test_repeated_post_above_tying_topic_in_one_file_is_not_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            _write_shared_post_export(inbox)
            digests = inbox / "digests"
            digests.mkdir()
            body = _topic("https://t.me/sharedname/50", checked=True) + _topic(
                "https://t.me/sharedname/77", checked=True
            )
            (digests / "Telegram Digest 21_06_2026.md").write_text(
                _section("One file", body),
                encoding="utf-8",
            )

            counts = load_useful_counts(inbox)
            self.assertEqual(counts["111"], 1)
            self.assertEqual(counts["222"], 0)

    def test_shared_msg_counts_only_for_heading_with_username(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            export = inbox / "channels" / "2026-06.md"
            export.parent.mkdir(parents=True)
            export.write_text(
                _export_heading("ozman", "1627768519", 7429, username="ozmanofficial")
                + _export_heading("антонов-такой-антонов", "1324711820", 7429)
                + _export_heading(
                    "captain-alumni-комьюнити-выпускников", "2210731208", 7429
                ),
                encoding="utf-8",
            )
            digests = inbox / "digests"
            digests.mkdir()
            (digests / "Telegram Digest 13_06_2026.md").write_text(
                _section(
                    "OZMAN",
                    _topic("https://t.me/ozmanofficial/7429", checked=True),
                ),
                encoding="utf-8",
            )

            counts = load_useful_counts(inbox)
            self.assertEqual(counts["1627768519"], 1)
            self.assertEqual(counts["1324711820"], 0)
            self.assertEqual(counts["2210731208"], 0)

    def test_username_on_one_message_does_not_count_another_shared_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            export = inbox / "channels" / "2026-06.md"
            export.parent.mkdir(parents=True)
            export.write_text(
                _export_heading("ozman", "1627768519", 7429, username="ozmanofficial")
                + _export_heading("ozman", "1627768519", 50)
                + _export_heading("антонов-такой-антонов", "1324711820", 7429)
                + _export_heading("антонов-такой-антонов", "1324711820", 50),
                encoding="utf-8",
            )
            digests = inbox / "digests"
            digests.mkdir()
            (digests / "Telegram Digest 13_06_2026.md").write_text(
                _section(
                    "OZMAN",
                    _topic("https://t.me/ozmanofficial/7429", checked=True),
                ),
                encoding="utf-8",
            )
            (digests / "Telegram Digest 20_09_2026.md").write_text(
                _section(
                    "OZMAN later",
                    _topic("https://t.me/ozmanofficial/50", checked=True),
                ),
                encoding="utf-8",
            )

            counts = load_useful_counts(inbox)
            self.assertEqual(counts["1627768519"], 1)
            self.assertEqual(counts["1324711820"], 0)


if __name__ == "__main__":
    unittest.main()
