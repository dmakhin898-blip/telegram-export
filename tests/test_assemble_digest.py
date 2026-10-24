#!/usr/bin/env python3
"""Prove assemble_digest validates callouts and can assemble a mini digest."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from assemble_digest import assemble  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class AssembleDigestTests(unittest.TestCase):
    def _copy_fixture(self, name: str, dest: Path) -> None:
        src = FIXTURES / name
        for path in src.iterdir():
            shutil.copy(path, dest / path.name)

    def test_valid_fixture_assembles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            build_root = tmp_path / "_build"
            dated = build_root / "01_01_2099"
            dated.mkdir(parents=True)
            self._copy_fixture("valid", dated)
            inbox = tmp_path / "inbox"

            out = assemble(
                "01_01_2099",
                write=True,
                inbox_dir=inbox,
                build_root=build_root,
            )
            self.assertIsNotNone(out)
            assert out is not None
            text = out.read_text(encoding="utf-8")
            self.assertIn("# Telegram Digest 01_01_2099", text)
            self.assertIn("### Ещё темы Alumni", text)
            self.assertIn("### Ещё темы", text)
            self.assertIn("_Ещё 1 не вошло в подборку._", text)

    def test_thin_context_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            build_root = tmp_path / "_build"
            dated = build_root / "01_01_2099"
            dated.mkdir(parents=True)
            self._copy_fixture("valid", dated)

            other_path = dated / "other_batch_01.json"
            data = json.loads(other_path.read_text(encoding="utf-8"))
            data["channels"][0]["topics"][0]["context"] = "Короткий повтор тизера."
            other_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            inbox = tmp_path / "inbox"
            digest_path = inbox / "digests" / "Telegram Digest 01_01_2099.md"

            with self.assertRaises(SystemExit) as ctx:
                assemble(
                    "01_01_2099",
                    write=True,
                    inbox_dir=inbox,
                    build_root=build_root,
                )
            self.assertEqual(ctx.exception.code, 1)
            self.assertFalse(digest_path.exists())

    def test_headings_show_useful_count_including_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            build_root = tmp_path / "_build"
            dated = build_root / "01_01_2099"
            dated.mkdir(parents=True)
            self._copy_fixture("valid", dated)

            thick = {
                "problem": "Команда оптимизирует просмотры вместо удержания и оплаты.",
                "context": (
                    "В посте сравниваются два дашборда: один с охватом, другой с "
                    "activation и paywall view. Автор показывает, как рост охвата "
                    "маскировал падение доходимости до оплаты. Приведены цифры за "
                    "две недели и короткий разбор воронки."
                ),
                "solution": (
                    "Перенести фокус на activation → paywall view → checkout. "
                    "Vanity-метрики оставить как вторичный слой."
                ),
            }

            def channel(name: str, url: str) -> dict:
                return {
                    "name": name,
                    "short_name": name,
                    "topics": [
                        {
                            "teaser": "Автор разбирает ловушку метрик в еженедельном отчёте.",
                            "url": url,
                            **thick,
                        }
                    ],
                    "more_topics": [],
                    "omitted_count": 0,
                }

            tier2 = {
                "channels": [
                    channel("Example Zero", "https://t.me/zero_author/201"),
                    channel("Example High", "https://t.me/high_author/101"),
                ]
            }
            (dated / "tier_2.json").write_text(
                json.dumps(tier2, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            alumni = json.loads((dated / "alumni.json").read_text(encoding="utf-8"))
            late = channel("Example Alumni Late", "https://t.me/high_author/101")
            late["topics"][0]["theme"] = "Late theme"
            alumni["channels"].append(late)
            (dated / "alumni.json").write_text(
                json.dumps(alumni, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            inbox = tmp_path / "inbox"
            export = inbox / "high-author" / "2026-01.md"
            export.parent.mkdir(parents=True)
            export_lines = []
            for message_id in range(101, 108):
                export_lines.append(
                    f"## 2026-01-01 00:00:00 UTC | high-author ({7001}) | msg:{message_id}\n\n"
                    "post\n\n---\n"
                )
            export_lines.append(
                "## 2026-01-01 00:00:00 UTC | zero-author (7002) | msg:201\n\npost\n\n---\n"
            )
            export.write_text("".join(export_lines), encoding="utf-8")

            digests = inbox / "digests"
            digests.mkdir()
            prior_topics = []
            for message_id in range(101, 108):
                url = f"https://t.me/high_author/{message_id}"
                prior_topics.append(
                    "\n".join(
                        [
                            f"**High** — [пост]({url}): Синтез.",
                            "- [ ] Почитать в телеграмме",
                            "",
                            "> - [x] Полезно",
                            ">",
                            f"> → [Читать в Telegram]({url})",
                            "",
                        ]
                    )
                )
            (digests / "Telegram Digest 01_12_2098.md").write_text(
                "### Старое имя High\n\n" + "\n".join(prior_topics),
                encoding="utf-8",
            )
            destination = digests / "Telegram Digest 01_01_2099.md"
            replaced_url = "https://t.me/high_author/101"
            destination.write_text(
                "\n".join(
                    [
                        "### Старое имя High",
                        "",
                        f"**High** — [пост]({replaced_url}): Синтез.",
                        "> - [x] Полезно",
                        f"> → [Читать в Telegram]({replaced_url})",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            out = assemble(
                "01_01_2099",
                write=True,
                inbox_dir=inbox,
                build_root=build_root,
            )
            self.assertIsNotNone(out)
            assert out is not None
            text = out.read_text(encoding="utf-8")
            self.assertIn("### Example High · 7", text)
            self.assertIn("### Example Zero · 0", text)
            self.assertIn("### Example Alumni Community · 0", text)
            self.assertIn("### Example Alumni Late · 7", text)
            self.assertLess(
                text.index("### Example High · 7"),
                text.index("### Example Zero · 0"),
            )
            self.assertLess(
                text.index("### Example Alumni Community · 0"),
                text.index("### Example Alumni Late · 7"),
            )
            self.assertNotIn("7001", text)
            self.assertNotIn("7002", text)
            self.assertNotIn("[x] Полезно", text)
            self.assertIn("[ ] Полезно", text)


if __name__ == "__main__":
    unittest.main()
