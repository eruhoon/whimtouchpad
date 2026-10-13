#!/usr/bin/env python3
"""Regression parity test: verifies XML layout and Controller cells 100% match legacy hardcoded cells."""
import sys
import unittest
from pathlib import Path

# Add template directory to PYTHONPATH
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'template'
sys.path.insert(0, str(TEMPLATE_DIR))

from controller import Controller
from layout_loader import LayoutLoader

def expected_build_cells(mode):
    cells = [(397, 6, 54, 54, 'Pad'), (457, 6, 54, 54, 'Keys'), (517, 6, 54, 54, 'Settings'), (577, 6, 54, 54, 'Sleep')]
    if mode == 'pad':
        return cells + [(9, 400, 257, 76, 'L Click'), (275, 400, 90, 76, 'Wheel'), (374, 400, 257, 76, 'R Click')]
    if mode == 'settings':
        return cells + [(18, 132, 90, 58, 'Gain-'), (532, 132, 90, 58, 'Gain+'), (18, 212, 604, 52, 'Natural'), (18, 276, 604, 52, 'ScreenTimeout'), (18, 365, 604, 68, 'Return')]
    rows = [['Esc'] + ['F' + str(i) for i in range(1, 13)], list('`1234567890-=') + ['Back'], ['Tab'] + list('qwertyuiop[]\\'), ['Caps'] + list("asdfghjkl;'") + ['Enter'], ['Shift'] + list('zxcvbnm,./') + ['Shift'], ['Ctrl', 'Alt', 'Space', 'EN/KR', 'Del', 'Home', 'End']]
    y = 66
    heights = [47, 72, 72, 72, 72, 75]
    for row, h in zip(rows, heights):
        weights = [3.8 if k == 'Space' else 1.05 if k == 'EN/KR' else 1.5 if k in ['Enter', 'Back', 'Shift'] else 1 for k in row]
        unit = 626 / sum(weights)
        x = 7
        for k, weight in zip(row, weights):
            w = unit * weight
            cells.append((x + 2, y + 2, w - 4, h - 4, k))
            x += w
        y += h
    return cells

class TestLayoutParity(unittest.TestCase):
    def setUp(self):
        self.loader = LayoutLoader(TEMPLATE_DIR / 'layouts' / 'default.xml')
        self.ctl = Controller(lambda msg: None, layout_loader=self.loader)

    def test_pad_mode_parity(self):
        legacy = expected_build_cells('pad')
        xml_cells = list(self.loader.get_cells('pad'))
        self.ctl.mode = 'pad'
        ctl_cells = list(self.ctl.cells())

        self.assertEqual(legacy, xml_cells)
        self.assertEqual(legacy, ctl_cells)

    def test_settings_mode_parity(self):
        legacy = expected_build_cells('settings')
        xml_cells = list(self.loader.get_cells('settings'))
        self.ctl.mode = 'settings'
        ctl_cells = list(self.ctl.cells())

        self.assertEqual(legacy, xml_cells)
        self.assertEqual(legacy, ctl_cells)

    def test_keys_mode_parity(self):
        legacy = expected_build_cells('keys')
        xml_cells = list(self.loader.get_cells('keys'))
        self.ctl.mode = 'keys'
        ctl_cells = list(self.ctl.cells())

        self.assertEqual(len(legacy), len(xml_cells))
        self.assertEqual(len(legacy), len(ctl_cells))
        for i, (leg, xml, ctl_c) in enumerate(zip(legacy, xml_cells, ctl_cells)):
            self.assertEqual(leg, xml, f"Mismatch in key #{i} (xml)")
            self.assertEqual(leg, ctl_c, f"Mismatch in key #{i} (controller)")

if __name__ == '__main__':
    unittest.main()
