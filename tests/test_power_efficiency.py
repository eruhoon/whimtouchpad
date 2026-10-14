import unittest
import sys
import os
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from screen_idle import ScreenIdle
from backlight import Backlight
from ui import calc_adaptive_timeout

class TestPowerEfficiency(unittest.TestCase):
    def test_adaptive_timeout_states(self):
        now = 100.0

        # 1. Active state (recent activity within 1.0s)
        timeout, is_active = calc_adaptive_timeout(now, last_active=99.5, is_blank=False, has_pending=False)
        self.assertAlmostEqual(timeout, 1 / 60)
        self.assertTrue(is_active)

        # 2. Idle state (no activity for >= 1.0s)
        timeout, is_active = calc_adaptive_timeout(now, last_active=98.5, is_blank=False, has_pending=False)
        self.assertAlmostEqual(timeout, 0.3)
        self.assertFalse(is_active)

        # 3. Sleep state (blank screen)
        timeout, is_active = calc_adaptive_timeout(now, last_active=99.9, is_blank=True, has_pending=False)
        self.assertAlmostEqual(timeout, 0.5)
        self.assertFalse(is_active)

        # 4. Pending state (scheduled timers due in 10ms)
        timeout, is_active = calc_adaptive_timeout(now, last_active=90.0, is_blank=False, has_pending=True, next_due=100.010)
        self.assertAlmostEqual(timeout, 0.010, places=3)
        self.assertTrue(is_active)

    def test_screen_idle_power_integration(self):
        power_history = []
        def on_power(state):
            power_history.append(state)

        idle = ScreenIdle(now=10.0, timeout=5, on_power_change=on_power)
        self.assertFalse(idle.blank)
        self.assertEqual(len(power_history), 0)

        # Tick before timeout: still awake
        idle.tick(now=14.0, busy=False)
        self.assertFalse(idle.blank)
        self.assertEqual(len(power_history), 0)

        # Tick at timeout (now - last = 5 >= 5): transitions to blank
        is_blank = idle.tick(now=15.0, busy=False)
        self.assertTrue(is_blank)
        self.assertTrue(idle.blank)
        self.assertEqual(power_history, [False])

        # Touch on blank screen: wakes up screen and swallows touch
        consumed = idle.consume(contacts=1, now=16.0)
        self.assertTrue(consumed)
        self.assertFalse(idle.blank)
        self.assertEqual(power_history, [False, True])

        # Release wake touch: still swallowed
        consumed = idle.consume(contacts=0, now=16.1)
        self.assertTrue(consumed)

        # Normal touch after waking: not swallowed
        consumed = idle.consume(contacts=1, now=16.5)
        self.assertFalse(consumed)

        # Explicit sleep button click (blank = True)
        idle.blank = True
        self.assertEqual(power_history, [False, True, False])

        # Reset screen
        idle.reset(now=20.0)
        self.assertFalse(idle.blank)
        self.assertEqual(power_history, [False, True, False, True])

    @patch('subprocess.run')
    def test_backlight_controller(self, mock_run):
        bl = Backlight(output="DSI-1")
        self.assertTrue(bl.powered)

        # Turn power off
        bl.set_power(False)
        self.assertFalse(bl.powered)

        # Duplicate power off call should be ignored
        bl.set_power(False)
        self.assertFalse(bl.powered)

        # Wait briefly for worker thread execution
        time.sleep(0.05)
        mock_run.assert_called_with(
            ["swaymsg", "output", "DSI-1", "power", "off"],
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
            check=False,
            timeout=1.0,
        )

        # Restore / Turn power back on
        bl.restore()
        self.assertTrue(bl.powered)
        time.sleep(0.05)
        mock_run.assert_called_with(
            ["swaymsg", "output", "DSI-1", "power", "on"],
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
            check=False,
            timeout=1.0,
        )

if __name__ == '__main__':
    unittest.main()
