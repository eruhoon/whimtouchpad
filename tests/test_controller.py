#!/usr/bin/env python3
"""Controller unit test: verifies touch hit detection, mode switching, and input dispatch."""
import sys
import unittest
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'template'
sys.path.insert(0, str(TEMPLATE_DIR))

from controller import Controller

class TestControllerBehavior(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.ctl = Controller(lambda msg: self.sent.append(msg))

    def test_hit_detection(self):
        # 4-icon toolbar header buttons
        self.assertEqual(self.ctl.hit(420, 30), 'Pad')
        self.assertEqual(self.ctl.hit(480, 30), 'Keys')
        self.assertEqual(self.ctl.hit(540, 30), 'Settings')
        self.assertEqual(self.ctl.hit(600, 30), 'Sleep')

        # Pad buttons
        self.assertEqual(self.ctl.hit(10, 420), 'L Click')
        self.assertEqual(self.ctl.hit(280, 420), 'Wheel')
        self.assertEqual(self.ctl.hit(380, 420), 'R Click')

        # Empty pad area and top-left title area
        self.assertIsNone(self.ctl.hit(200, 200))
        self.assertIsNone(self.ctl.hit(50, 30))

    def test_mode_switch(self):
        self.assertEqual(self.ctl.mode, 'pad')
        self.assertTrue(self.ctl.active('Pad'))
        self.assertFalse(self.ctl.active('Keys'))

        # Tap Keys icon
        self.ctl.keytap('Keys', 1.0)
        self.assertEqual(self.ctl.mode, 'keys')
        self.assertFalse(self.ctl.active('Pad'))
        self.assertTrue(self.ctl.active('Keys'))

        # Tap Pad icon
        self.ctl.keytap('Pad', 2.0)
        self.assertEqual(self.ctl.mode, 'pad')
        self.assertTrue(self.ctl.active('Pad'))
        self.assertFalse(self.ctl.active('Keys'))

        # Settings switch
        self.ctl.keytap('Settings', 3.0)
        self.assertEqual(self.ctl.mode, 'settings')
        self.ctl.keytap('Return', 4.0)
        self.assertEqual(self.ctl.mode, 'pad')

    def test_mouse_button_dispatch(self):
        # Press Left Click
        self.ctl.frame(1, 10, 420, 1.0)
        self.assertTrue(any('m 0 0 1' in m for m in self.sent), "Left click down not sent")

        # Release Left Click
        self.sent.clear()
        self.ctl.frame(0, 10, 420, 1.1)
        self.ctl.tick(1.2)
        self.assertTrue(any('m 0 0 0' in m for m in self.sent), "Left click release not sent")

    def test_key_dispatch(self):
        self.ctl.mode = 'keys'
        self.sent.clear()
        self.ctl.keytap('Esc', 1.0)
        # Linux keycode for Esc is 1
        self.assertTrue(any('k 1 1' in m for m in self.sent), "Key press not sent")
        self.ctl.tick(1.1)
        self.assertTrue(any('k 1 0' in m for m in self.sent), "Key release not sent")

    def test_direct_macro_dispatch(self):
        self.sent.clear()
        self.ctl._send_macro("Up,wait:100,Space", t=1.0, interval=0.05)
        # First key at 1.0
        self.ctl.tick(1.0)
        self.assertIn('k 103 1', self.sent) # Up (103) down
        self.ctl.tick(1.03)
        self.assertIn('k 103 0', self.sent) # Up up
        # wait:100ms -> next key at 1.0 + 0.05 + 0.10 = 1.15
        self.sent.clear()
        self.ctl.tick(1.10)
        self.assertEqual(len(self.sent), 0)
        self.ctl.tick(1.15)
        self.assertIn('k 57 1', self.sent) # Space (57) down

    def test_toggle_and_hold_cleanup_on_close(self):
        # Set active toggle and hold
        self.ctl.toggle_states['custom_toggle'] = True
        self.ctl.active_holds.add(('custom_hold', 29)) # Ctrl held
        self.sent.clear()
        self.ctl.close()
        # Must release Ctrl (29)
        self.assertTrue(any('k 29 0' in m for m in self.sent))
        self.assertEqual(len(self.ctl.toggle_states), 0)
        self.assertEqual(len(self.ctl.active_holds), 0)

if __name__ == '__main__':
    unittest.main()
