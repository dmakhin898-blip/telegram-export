#!/usr/bin/env python3
"""Heading shapes and the stamp pass that adds @username without new posts."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common import (  # noqa: E402
    format_message_block,
    heading_channel_key,
    parse_export_heading,
)
from export_channels import stamp_export_usernames  # noqa: E402
from telethon.errors import UnauthorizedError  # noqa: E402


def _message(message_id: int, text: str = "hello"):
    return SimpleNamespace(
        date=datetime(2026, 6, 5, 15, 12, 19, tzinfo=timezone.utc),
        id=message_id,
        message=text,
    )


class _Entity:
    def __init__(self, username: str | None) -> None:
        self.username = username


class _Client:
    def __init__(self, usernames: dict[str, str | None]) -> None:
        self._usernames = usernames
        self.calls: list[object] = []

    async def get_entity(self, ref: object) -> _Entity:
        self.calls.append(ref)
        channel_id = str(ref)
        if channel_id.startswith("-100"):
            channel_id = channel_id[4:]
        return _Entity(self._usernames.get(channel_id))


class HeadingFormatTests(unittest.TestCase):
    def test_channel_without_username_exports_slug_and_id(self) -> None:
        key = heading_channel_key("private-channel", "42", None)
        self.assertEqual(key, "private-channel (42)")
        block = format_message_block(key, _message(8))
        self.assertIn("private-channel (42) | msg:8", block)
        self.assertNotIn("@", block)

        blank = heading_channel_key("private-channel", "42", "  ")
        self.assertEqual(blank, "private-channel (42)")

    def test_public_channel_heading_includes_username(self) -> None:
        key = heading_channel_key("ozman", "1627768519", "@ozmanofficial")
        block = format_message_block(key, _message(7429))
        self.assertIn(
            "ozman (@ozmanofficial) (1627768519) | msg:7429",
            block,
        )
        parsed = parse_export_heading(block.splitlines()[0])
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.channel_id, "1627768519")
        self.assertEqual(parsed.message_id, 7429)
        self.assertEqual(parsed.username, "ozmanofficial")

    def test_both_heading_shapes_parse(self) -> None:
        bare = parse_export_heading(
            "## 2025-05-15 08:15:46 UTC | "
            "captain-alumni-комьюнити-выпускников (2210731208) | msg:7429"
        )
        named = parse_export_heading(
            "## 2026-06-05 15:12:19 UTC | "
            "ozman (@ozmanofficial) (1627768519) | msg:7429"
        )
        self.assertIsNotNone(bare)
        self.assertIsNotNone(named)
        assert bare is not None and named is not None
        self.assertIsNone(bare.username)
        self.assertEqual(bare.channel_id, "2210731208")
        self.assertEqual(bare.message_id, 7429)
        self.assertEqual(named.username, "ozmanofficial")
        self.assertEqual(named.slug, "ozman")


class StampUsernameTests(unittest.TestCase):
    def test_stamp_rewrites_public_headings_without_appending_or_touching_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            first = inbox / "ozman" / "2026-06.md"
            second = inbox / "ozman" / "2026-07.md"
            first.parent.mkdir(parents=True)
            body = (
                "## 2026-06-05 15:12:19 UTC | ozman (1627768519) | msg:7429\n\n"
                "keep this body\n\n---\n"
                "## 2026-06-06 00:00:00 UTC | ozman (@ozmanofficial) (1627768519) | msg:7430\n\n"
                "already stamped\n\n---\n"
            )
            first.write_text(body, encoding="utf-8")
            second.write_text(
                "## 2026-07-01 00:00:00 UTC | ozman (1627768519) | msg:7500\n\n"
                "july body\n\n---\n"
                "## 2026-07-02 00:00:00 UTC | private-channel (99) | msg:1\n\n"
                "private body\n\n---\n",
                encoding="utf-8",
            )
            digest = inbox / "digests" / "Telegram Digest 13_06_2026.md"
            digest.parent.mkdir()
            digest_text = (
                "## 2026-06-05 15:12:19 UTC | ozman (1627768519) | msg:7429\n"
            )
            digest.write_text(digest_text, encoding="utf-8")
            state = inbox / ".export_state.json"
            state_text = (
                '{"1627768519": {"last_export_at": "2026-06-01T00:00:00+00:00"}}\n'
            )
            state.write_text(state_text, encoding="utf-8")

            client = _Client(
                {"1627768519": "ozmanofficial", "99": None},
            )
            rewritten = asyncio.run(stamp_export_usernames(inbox, client))

            self.assertEqual(rewritten, 2)
            self.assertEqual(len(client.calls), 2)
            stamped = first.read_text(encoding="utf-8")
            self.assertIn(
                "ozman (@ozmanofficial) (1627768519) | msg:7429",
                stamped,
            )
            self.assertIn("keep this body", stamped)
            self.assertEqual(stamped.count("msg:7429"), 1)
            self.assertEqual(stamped.count("@ozmanofficial"), 2)
            self.assertIn("already stamped", stamped)
            july = second.read_text(encoding="utf-8")
            self.assertIn(
                "ozman (@ozmanofficial) (1627768519) | msg:7500",
                july,
            )
            self.assertIn("private-channel (99) | msg:1", july)
            self.assertNotIn("@", july.split("private body")[0].split("msg:7500")[-1])
            self.assertIn("july body", july)
            self.assertIn("private body", july)
            self.assertEqual(digest.read_text(encoding="utf-8"), digest_text)
            self.assertEqual(state.read_text(encoding="utf-8"), state_text)
            self.assertEqual(list(inbox.rglob("*.stamp-tmp")), [])

            client.calls.clear()
            again = asyncio.run(stamp_export_usernames(inbox, client))
            self.assertEqual(again, 0)
            self.assertEqual(
                [str(ref) for ref in client.calls],
                ["-10099"],
            )
            self.assertEqual(first.read_text(encoding="utf-8"), stamped)
            self.assertEqual(state.read_text(encoding="utf-8"), state_text)

    def test_auth_failure_does_not_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            path = inbox / "ozman" / "2026-06.md"
            path.parent.mkdir(parents=True)
            original = (
                "## 2026-06-05 15:12:19 UTC | ozman (1627768519) | msg:7429\n\n"
                "keep this body\n\n---\n"
            )
            path.write_text(original, encoding="utf-8")

            class _AuthClient:
                async def get_entity(self, ref: object) -> _Entity:
                    raise UnauthorizedError(None, "session is not authorized")

            with self.assertRaises(UnauthorizedError):
                asyncio.run(stamp_export_usernames(inbox, _AuthClient()))
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
