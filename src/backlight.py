"""Hardware backlight and display power manager for Rocknix / Dual-Screen handhelds."""
import os
import subprocess
import threading
from pathlib import Path

class Backlight:
    def __init__(self, output=None):
        self.output = output or os.environ.get("WHIMPAD_BOTTOM_OUTPUT", "DSI-1")
        self.powered = True
        self.sysfs_node = self._find_sysfs_node()
        self._lock = threading.Lock()

    def _find_sysfs_node(self):
        try:
            bl_dir = Path("/sys/class/backlight")
            if not bl_dir.exists():
                return None
            nodes = [p for p in bl_dir.iterdir() if p.is_dir()]
            if not nodes:
                return None
            for node in nodes:
                name = node.name.lower()
                if "dsi" in name or "panel" in name or "bottom" in name:
                    return node
            return nodes[0]
        except Exception:
            return None

    def set_power(self, power: bool):
        with self._lock:
            if self.powered == power:
                return
            self.powered = power
        # Launch non-blocking worker thread so the UI loop never hitches
        threading.Thread(target=self._apply_power, args=(power,), daemon=True).start()

    def _apply_power(self, power: bool):
        state = "on" if power else "off"
        # 1. Sway Wayland output power toggle
        try:
            subprocess.run(
                ["swaymsg", "output", self.output, "power", state],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=1.0,
            )
        except Exception:
            pass

        # 2. Linux Sysfs backlight toggle (bl_power: 0=on, 1=off)
        if self.sysfs_node:
            try:
                bl_power = self.sysfs_node / "bl_power"
                if bl_power.exists():
                    bl_power.write_text("0" if power else "1")
            except Exception:
                pass

    def restore(self):
        """Ensure backlight is restored on shutdown/cleanup."""
        self.set_power(True)
