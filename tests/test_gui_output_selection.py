"""The GUI may accept an existing destination folder without overwriting it."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from install_gui import choose_output_root


class GuiOutputSelection(unittest.TestCase):
    def test_existing_folder_gets_new_child(self):
        with tempfile.TemporaryDirectory() as td:
            existing=Path(td)/'새 폴더 (3)'
            existing.mkdir()
            marker=existing/'keep.txt'
            marker.write_text('기존 파일 보존',encoding='utf-8')
            result=choose_output_root(existing)
            self.assertEqual(result,existing/'Fallout34-Korean-Output')
            self.assertFalse(result.exists())
            self.assertEqual(marker.read_text('utf-8'),'기존 파일 보존')

    def test_second_run_uses_unique_folder_without_touching_old(self):
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)
            old=parent/'Fallout34-Korean-Output'
            old.mkdir()
            (old/'build-report.json').write_text('ORIGINAL',encoding='utf-8')
            self.assertEqual(choose_output_root(parent),parent/'Fallout34-Korean-Output (2)')
            (parent/'Fallout34-Korean-Output (2)').mkdir()
            self.assertEqual(choose_output_root(parent),parent/'Fallout34-Korean-Output (3)')
            self.assertEqual((old/'build-report.json').read_text('utf-8'),'ORIGINAL')

    def test_nonexistent_explicit_path_remains_exact(self):
        with tempfile.TemporaryDirectory() as td:
            custom=Path(td)/'내가 지정한 새 이름'
            self.assertEqual(choose_output_root(custom),custom)
            self.assertFalse(custom.exists())

    def test_existing_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            existing=Path(td)/'something.txt'
            existing.write_text('KEEP',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'폴더가 아닙니다'):
                choose_output_root(existing)
            self.assertEqual(existing.read_text('utf-8'),'KEEP')


if __name__=='__main__':
    unittest.main()
