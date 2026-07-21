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


if __name__ == "__main__":
    unittest.main()
