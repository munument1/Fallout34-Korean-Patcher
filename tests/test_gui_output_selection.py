"""The GUI may accept an existing destination folder without overwriting it."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from install_gui import choose_output_root,resolve_esm_folder,normalize_pasted_path


class GuiOutputSelection(unittest.TestCase):
    def test_quoted_windows_explorer_path_is_cleaned(self):
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)/'Desktop'/'새 폴더 (3)'
            parent.mkdir(parents=True)
            self.assertEqual(normalize_pasted_path(f'  "{parent}"  ','출력 폴더'),parent)
            self.assertEqual(choose_output_root(normalize_pasted_path(f'"{parent}"','출력 폴더')),
                             parent/'Fallout34-Korean-Output')

    def test_invalid_embedded_quotes_report_helpful_error(self):
        with self.assertRaisesRegex(ValueError,'큰따옴표'):
            normalize_pasted_path('"C:\\Example"\\bad"','출력 폴더')

    def test_single_quotes_around_path_are_also_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(normalize_pasted_path(f"'{td}'",'출력 폴더'),Path(td))

    def test_esm_source_folder_resolves_both_files(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'Fallout 4'/'Data'
            source.mkdir(parents=True)
            fo3=source/'Fallout34.esm'
            nv=source/'FalloutNV34.esm'
            fo3.write_bytes(b'source only')
            nv.write_bytes(b'source only')
            self.assertEqual(resolve_esm_folder(str(source)),(fo3,nv))
            self.assertEqual(resolve_esm_folder('"'+str(source)+'"'),(fo3,nv))

    def test_single_file_selected_instead_of_folder_is_rejected_with_hint(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'Fallout34.esm'
            file.write_bytes(b'example')
            with self.assertRaisesRegex(ValueError,'폴더를 선택'):
                resolve_esm_folder(str(file))

    def test_missing_companion_esm_reports_folder_and_file(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)
            (source/'Fallout34.esm').write_bytes(b'example')
            with self.assertRaises(ValueError) as caught:
                resolve_esm_folder(str(source))
            self.assertIn('falloutnv34.esm',str(caught.exception))
            self.assertIn(str(source),str(caught.exception))

    def test_empty_source_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'폴더를 선택'):
            resolve_esm_folder('  ')

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
