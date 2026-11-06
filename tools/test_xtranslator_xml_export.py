"""Verify the stock xTranslator SSTXMLRessources v2 roundtrip shape."""
from io import StringIO
import unittest
import xml.etree.ElementTree as ET

from export_xtranslator_xml import (
    xml_text, write_entry, write_footer, write_header,
)


class XTranslatorXMLExport(unittest.TestCase):
    def test_real_format_source_dest_and_xml_escaping(self):
        english = "A & B\r\n<Global=F34_Unit> \"quote\""
        korean = "가 & 나\r\n<Global=F34_Unit> '따옴표'"
        out = StringIO()
        write_header(out, "Fallout34.esm")
        write_entry(out, "Fo3Quest01", "QUST", "NNAM", 1, 3, english, korean)
        write_footer(out)
        root = ET.fromstring(out.getvalue())
        self.assertEqual(root.tag, "SSTXMLRessources")
        self.assertEqual(root.findtext("./Params/Addon"), "Fallout34.esm")
        self.assertEqual(root.findtext("./Params/Source"), "en")
        self.assertEqual(root.findtext("./Params/Dest"), "ko")
        self.assertEqual(root.findtext("./Params/Version"), "2")
        entry = root.find("./Content/String")
        self.assertEqual(entry.attrib["List"], "0")
        self.assertEqual(entry.findtext("Source"), english)
        self.assertEqual(entry.findtext("Dest"), korean)
        self.assertEqual(entry.find("REC").attrib, {"id": "2", "idMax": "3"})
        self.assertEqual(entry.findtext("REC"), "QUST:NNAM")
        self.assertEqual(entry.findtext("EDID"), "Fo3Quest01")

    def test_single_field_uses_bare_rec_and_bracket_formid(self):
        out = StringIO()
        write_header(out, "FalloutNV34.esm")
        write_entry(out, "[0100ABCD]", "MISC", "FULL", 0, 1, "Med-X", "메드-X")
        write_footer(out)
        record = ET.fromstring(out.getvalue()).find("./Content/String")
        self.assertEqual(record.findtext("EDID"), "[0100ABCD]")
        self.assertEqual(record.find("REC").attrib, {})
        self.assertEqual(record.findtext("Dest"), "메드-X")

    def test_invalid_xml_control_char_rejected(self):
        with self.assertRaises(ValueError):
            xml_text("A\x01B")
        self.assertEqual(xml_text("A & B\r\n"), "A &amp; B&#13;\n")


if __name__ == "__main__":
    unittest.main()
