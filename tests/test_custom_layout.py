#!/usr/bin/env python3
"""Custom layout unit test: verifies dynamic 5-button injection, auto-grid layout, hotkey combos, and fail-safe."""
import sys
import tempfile
import unittest
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'template'
sys.path.insert(0, str(TEMPLATE_DIR))

from controller import Controller
from layout_loader import LayoutLoader

class TestCustomLayoutSystem(unittest.TestCase):
    def test_default_without_custom(self):
        loader = LayoutLoader(TEMPLATE_DIR / 'layouts' / 'default.xml', custom_xml_path=None)
        self.assertFalse(loader.has_custom)
        # 4 header buttons
        self.assertEqual(len(loader.header_cells), 4)
        self.assertEqual([k for _, _, _, _, k in loader.header_cells], ['Pad', 'Keys', 'Settings', 'Sleep'])
        self.assertEqual(loader.header_cells[0][0], 397) # Pad starts at 397

    def test_dynamic_custom_injection_and_grid(self):
        sample_path = TEMPLATE_DIR / 'layouts' / 'sample_rpg.xml'
        loader = LayoutLoader(TEMPLATE_DIR / 'layouts' / 'default.xml', custom_xml_path=sample_path)
        self.assertTrue(loader.has_custom)
        self.assertEqual(loader.custom_title, 'RPG 단축키')
        self.assertEqual(loader.default_view, 'custom')

        # 5 header buttons
        self.assertEqual(len(loader.header_cells), 5)
        self.assertEqual([k for _, _, _, _, k in loader.header_cells], ['Pad', 'Custom', 'Keys', 'Settings', 'Sleep'])
        self.assertEqual(loader.header_cells[0][0], 337) # Pad shifts to 337
        self.assertEqual(loader.header_cells[1][0], 397) # Custom at 397

        # Custom view cells: 5 header + 4 absolute buttons + 8 grid buttons = 17 cells
        custom_cells = loader.get_cells('custom')
        self.assertEqual(len(custom_cells), 17)

        ctl = Controller(lambda msg: None, layout_loader=loader)
        # default_view was 'custom', so ctl.mode should start at 'custom'
        self.assertEqual(ctl.mode, 'custom')
        self.assertTrue(ctl.active('Custom'))
        self.assertFalse(ctl.active('Pad'))

        # Header hit detection
        self.assertEqual(ctl.hit(360, 30), 'Pad')
        self.assertEqual(ctl.hit(420, 30), 'Custom')
        self.assertEqual(ctl.hit(480, 30), 'Keys')

    def test_combo_action_dispatch(self):
        sample_path = TEMPLATE_DIR / 'layouts' / 'sample_rpg.xml'
        loader = LayoutLoader(TEMPLATE_DIR / 'layouts' / 'default.xml', custom_xml_path=sample_path)
        sent = []
        ctl = Controller(lambda msg: sent.append(msg), layout_loader=loader)

        # Trigger Ctrl+S button
        ctl.keytap('Ctrl+S', 1.0)
        # Verify Ctrl (29) down and S (31) down
        self.assertIn('k 29 1', sent, "Ctrl modifier down missing")
        self.assertIn('k 31 1', sent, "S key down missing")

        # Advance tick for release
        sent.clear()
        ctl.tick(1.1)
        self.assertIn('k 31 0', sent, "S key release missing")
        self.assertIn('k 29 0', sent, "Ctrl modifier release missing")

    def test_broken_xml_fail_safe(self):
        # Create a malformed XML file (unclosed tag)
        with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False) as f:
            f.write('<layout id="broken"><button x="10" y="10">Unclosed')
            broken_path = Path(f.name)

        try:
            loader = LayoutLoader(TEMPLATE_DIR / 'layouts' / 'default.xml', custom_xml_path=broken_path)
            # Must safely fall back without crash
            self.assertFalse(loader.has_custom)
            self.assertEqual(len(loader.header_cells), 4)
            self.assertEqual(loader.header_cells[0][0], 397)
        finally:
            broken_path.unlink(missing_ok=True)

    def test_gamedir_resolution_order(self):
        import os
        import shutil

        temp_dir = tempfile.mkdtemp()
        try:
            sample_xml = TEMPLATE_DIR / 'layouts' / 'sample_rpg.xml'

            # 1. Test GAMEDIR / whimpad.xml
            game_xml = Path(temp_dir) / 'whimpad.xml'
            shutil.copyfile(sample_xml, game_xml)

            os.environ['GAMEDIR'] = temp_dir
            loader = LayoutLoader(TEMPLATE_DIR / 'layouts' / 'default.xml', custom_xml_path=None)
            self.assertTrue(loader.has_custom)
            self.assertEqual(loader.custom_title, 'RPG 단축키')

            # 2. Test GAMEDIR / whimpad / whimpad.xml (nested fallback)
            game_xml.unlink()
            nested_dir = Path(temp_dir) / 'whimpad'
            nested_dir.mkdir()
            nested_xml = nested_dir / 'whimpad.xml'
            shutil.copyfile(sample_xml, nested_xml)

            loader2 = LayoutLoader(TEMPLATE_DIR / 'layouts' / 'default.xml', custom_xml_path=None)
            self.assertTrue(loader2.has_custom)
        finally:
            os.environ.pop('GAMEDIR', None)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_advanced_actions_and_sequential_macro(self):
        xml_content = """<layout id="adv_test" title="Advanced Actions" default="true">
  <button id="btn_toggle" x="10" y="80" w="60" h="50" type="toggle" key="Shift" />
  <button id="btn_hold" x="80" y="80" w="60" h="50" type="hold" key="Ctrl" />
  <button id="btn_long" x="150" y="80" w="60" h="50" key="F5" hold_action="key:F9" hold_time="400" />
  <button id="btn_macro" x="220" y="80" w="60" h="50" type="macro" sequence="Down,Right,Space" interval="50" />
  <button id="btn_turbo" x="290" y="80" w="60" h="50" type="turbo" key="Space" interval="60" />
</layout>"""
        with tempfile.NamedTemporaryFile('w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            adv_xml_path = Path(f.name)

        try:
            loader = LayoutLoader(TEMPLATE_DIR / 'layouts' / 'default.xml', custom_xml_path=adv_xml_path)
            self.assertTrue(loader.has_custom)
            self.assertEqual(loader.get_type('btn_toggle'), 'toggle')
            self.assertEqual(loader.get_type('btn_hold'), 'hold')
            self.assertEqual(loader.get_type('btn_macro'), 'macro')
            self.assertEqual(loader.get_button_meta('btn_macro')['sequence'], 'Down,Right,Space')
            self.assertEqual(loader.get_button_meta('btn_long')['hold_action'], 'key:F9')
            self.assertEqual(loader.get_button_meta('btn_long')['hold_time'], 0.4)

            sent = []
            ctl = Controller(lambda msg: sent.append(msg), layout_loader=loader)
            self.assertEqual(ctl.mode, 'adv_test')

            # 1. Test Toggle: Tap 1 -> down & active; Tap 2 -> up & inactive
            self.assertFalse(ctl.active('btn_toggle'))
            ctl.frame(1, 40, 100, 1.0)
            ctl.frame(0, 40, 100, 1.05)
            self.assertTrue(ctl.active('btn_toggle'))
            self.assertIn('k 42 1', sent)
            sent.clear()
            ctl.frame(1, 40, 100, 1.5)
            ctl.frame(0, 40, 100, 1.55)
            self.assertFalse(ctl.active('btn_toggle'))
            self.assertIn('k 42 0', sent)

            # 2. Test Hold: Touch down -> down; Touch up -> up
            sent.clear()
            ctl.frame(1, 100, 100, 2.0)
            self.assertIn('k 29 1', sent)
            sent.clear()
            ctl.frame(0, 100, 100, 2.3)
            self.assertIn('k 29 0', sent)

            # 3. Test Long-press:
            # 3a. Short tap (< 400ms) -> normal key F5 (63)
            sent.clear()
            ctl.frame(1, 170, 100, 3.0)
            ctl.frame(0, 170, 100, 3.1)
            self.assertIn('k 63 1', sent)
            self.assertNotIn('k 67 1', sent) # F9 not triggered

            # 3b. Long press (>= 400ms) -> hold_action F9 (67)
            sent.clear()
            ctl.frame(1, 170, 100, 4.0)
            ctl.tick(4.45)
            self.assertIn('k 67 1', sent) # F9 triggered!
            sent.clear()
            ctl.frame(0, 170, 100, 4.6) # Touch release
            self.assertNotIn('k 63 1', sent) # F5 must NOT be sent!

            # 4. Test Sequential Macro: Down -> Right -> Space
            sent.clear()
            ctl.frame(1, 240, 100, 5.0)
            ctl.frame(0, 240, 100, 5.05)
            ctl.tick(5.05)
            # Down (108) down
            self.assertIn('k 108 1', sent)
            # Advance to Down up (approx 5.08) and Right down (approx 5.10)
            ctl.tick(5.08)
            self.assertIn('k 108 0', sent)
            ctl.tick(5.10)
            self.assertIn('k 106 1', sent)
            ctl.tick(5.13)
            self.assertIn('k 106 0', sent)
            ctl.tick(5.15)
            self.assertIn('k 57 1', sent)
            ctl.tick(5.18)
            self.assertIn('k 57 0', sent)

            # 5. Test Turbo: repeats key while held
            sent.clear()
            ctl.frame(1, 310, 100, 6.0)
            self.assertIn('k 57 1', sent) # Initial burst
            sent.clear()
            ctl.tick(6.07)
            self.assertIn('k 57 1', sent) # Second burst
            ctl.frame(0, 310, 100, 6.1) # Release stops turbo
            ctl.tick(6.15) # Flushes release of last burst
            sent.clear()
            ctl.tick(6.3) # No more bursts should be scheduled
            self.assertEqual(len(sent), 0)
        finally:
            adv_xml_path.unlink(missing_ok=True)

if __name__ == '__main__':
    unittest.main()
