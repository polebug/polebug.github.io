"""Validate generated fonts against the exact original glyph outlines and metrics."""
import json
import unittest
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from subset import parse_ranges

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'blog/.font-cache'


def outline(font, cp):
    glyphs = font.getGlyphSet()
    pen = DecomposingRecordingPen(glyphs)
    glyphs[font.getBestCmap()[cp]].draw(pen)
    return pen.value


class SubsetValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((CACHE / 'subsets.json').read_text())
        cls.master = TTFont(CACHE / ('master-' + cls.manifest['sourceDigest'] + '.ttf'))
        records = [cls.manifest['shared']] + [p['font'] for p in cls.manifest['pages'].values() if p['font']]
        cls.records = {r['key']: r for r in records}.values()

    def test_character_coverage_metrics_and_outlines(self):
        master_cmap = self.master.getBestCmap()
        for record in self.records:
            with self.subTest(font=record['key']):
                font = TTFont(CACHE / Path(record['key']).name)
                points = parse_ranges(record['unicodeRange'])
                cmap = font.getBestCmap()
                self.assertEqual(points, set(cmap))
                for cp in points:
                    self.assertEqual(font['hmtx'][cmap[cp]], self.master['hmtx'][master_cmap[cp]])
                ordered = sorted(points)
                for cp in ordered[::max(1, len(ordered)//16)]:
                    self.assertEqual(outline(font, cp), outline(self.master, cp))
                font.close()

    def test_runtime_ui_labels_are_in_the_shared_font(self):
        config = json.loads((CACHE / 'input.json').read_text())
        lato = set(TTFont(config['lato']).getBestCmap())
        required = {ord(c) for c in config['uiText']} & set(self.master.getBestCmap()) - lato
        self.assertTrue(required.issubset(parse_ranges(self.manifest['shared']['unicodeRange'])))

    def test_shared_and_page_ranges_do_not_overlap(self):
        common = parse_ranges(self.manifest['shared']['unicodeRange'])
        for route, page in self.manifest['pages'].items():
            if page['font']:
                extra = parse_ranges(page['font']['unicodeRange'])
                self.assertFalse(common & extra, route)
                self.assertLessEqual(page['subsetBytes'], page['baselineBytes'], route)


if __name__ == '__main__':
    unittest.main()
