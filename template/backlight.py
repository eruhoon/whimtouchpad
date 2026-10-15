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
        # Explicit env override takes top priority
        custom_node = os.environ.get("WHIMPAD_BOTTOM_BACKLIGHT")
        if custom_node and Path(custom_node).exists():
            return Path(custom_node)

        try:
            bl_dir = Path("/sys/class/backlight")
            if not bl_dir.exists():
                return None
            nodes = [p for p in bl_dir.iterdir() if p.is_dir()]
            if not nodes:
                return None
            # CRITICAL: Only match nodes that explicitly designate the SECONDARY/BOTTOM panel.
            # Never fall back to nodes[0] (which controls the primary/top game screen).
            for node in nodes:
                name = node.name.lower()
                if any(k in name for k in ("pwm", "primary", "main", "top", "backlight-0")):
                    continue
                if any(k in name for k in ("dsi-1", "dsi1", "bottom", "secondary", "sub")):
                    return node
            return None
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
        # 1. Sway Wayland DPMS toggle (strictly targets secondary output e.g. DSI-1)
        # CRITICAL: Only use 'dpms', NEVER use 'power off' during runtime!
        # 'power off' disables the output in Sway, which migrates the WhimPad container
        # to the primary game screen (DSI-2), stealing focus from the game and triggering
        # unwanted pause/menu/button events in PortMaster games.
        if os.environ.get("WHIMPAD_DISABLE_DPMS", "0") != "1":
            try:
                subprocess.run(
                    ["swaymsg", "output", self.output, "dpms", state],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=1.0,
                )
            except Exception:
                pass


        # 2. Linux Sysfs backlight toggle (ONLY if verified secondary screen node)
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
