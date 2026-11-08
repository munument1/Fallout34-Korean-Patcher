"""Do not confuse a standalone patcher's location with unsafe output paths."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_mo2_korean_mod as backend


class OutputPathSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.desktop=Path(self.tmp.name)/'Desktop'
        self.exe_folder=self.desktop/'Fallout34-Korean-Patcher'
        self.exe_folder.mkdir(parents=True)
        self.data=Path(self.tmp.name)/'Games'/'Fallout 4'/'Data'
        self.data.mkdir(parents=True)
        self.sources={
            'fo3':self.data/'Fallout34.esm',
            'fnv':self.data/'FalloutNV34.esm',
        }

    def validate(self,out:Path,frozen:bool):
        with patch.object(backend,'ROOT',self.exe_folder), \
             patch.object(backend.sys,'frozen',frozen,create=True):
            backend.verify_directory_safety(self.sources,out)

    def test_standalone_can_write_to_a_new_child_beside_exe(self):
        self.validate(self.exe_folder/'Fallout34-Korean-Output',True)

    def test_standalone_can_write_to_desktop_sibling(self):
        self.validate(self.desktop/'Fallout34-Korean-Output',True)

    def test_standalone_can_write_under_a_user_selected_desktop_folder(self):
        destination=self.desktop/'새 폴더 (3)'/'Fallout34-Korean-Output'
        destination.parent.mkdir()
        self.validate(destination,True)

    def test_standalone_must_not_write_inside_packaged_resources(self):
        for name in ('assets','data','_internal','licenses'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,'bundled resources'):
                self.validate(self.exe_folder/name/'Fallout34-Korean-Output',True)

    def test_game_installation_and_original_data_remain_protected(self):
        for where in (self.data/'Fallout34-Korean-Output',
                      self.data.parent/'Fallout34-Korean-Output'):
            with self.subTest(where=where), self.assertRaisesRegex(ValueError,'game|ESM'):
                self.validate(where,True)

    def test_existing_target_is_still_rejected(self):
        folder=self.desktop/'Existing Output'
        folder.mkdir()
        with self.assertRaises(FileExistsError):
            self.validate(folder,True)

    def test_source_checkout_is_not_allowed_to_contain_output(self):
        with self.assertRaisesRegex(ValueError,'Source checkout'):
            self.validate(self.exe_folder/'Fallout34-Korean-Output',False)
        self.validate(self.desktop/'Fallout34-Korean-Output',False)


if __name__=='__main__':
    unittest.main()
