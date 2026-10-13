"""WhimPad layout loader: parses layout XML using xml.etree.ElementTree."""
from pathlib import Path
import os
import xml.etree.ElementTree as ET

class LayoutLoader:
    def __init__(self, xml_path=None, custom_xml_path=None):
        self.xml_path = Path(xml_path) if xml_path else Path(__file__).parent / 'layouts' / 'default.xml'
        self.custom_xml_path = self._resolve_custom_path(custom_xml_path)
        self.layouts = {}
        self.header_cells = []
        self.views = {}
        self.icons = {}
        self.actions = {}
        self.labels = {}
        self.has_custom = False
        self.custom_id = 'custom'
        self.custom_title = '게임 단축키'
        self.default_view = 'pad'
        self.reload()

    def _resolve_custom_path(self, explicit_path):
        if explicit_path:
            p = Path(explicit_path)
            if p.exists():
                return p
        env_custom = os.environ.get('WHIMPAD_CUSTOM_LAYOUT')
        if env_custom and Path(env_custom).exists():
            return Path(env_custom)
        gamedir = os.environ.get('GAMEDIR')
        if gamedir:
            candidate = Path(gamedir) / 'whimpad.xml'
            if candidate.exists():
                return candidate
            candidate_nested = Path(gamedir) / 'whimpad' / 'whimpad.xml'
            if candidate_nested.exists():
                return candidate_nested
        conf_candidate = Path(__file__).parent / 'conf' / 'custom_layout.xml'
        if conf_candidate.exists():
            return conf_candidate
        return None

    def reload(self):
        self.layouts = {}
        self.header_cells = []
        self.views = {}
        self.icons = {}
        self.actions = {}
        self.labels = {}
        self.has_custom = False
        self.default_view = 'pad'

        # 1. Base views from default.xml
        base_views = {}
        if self.xml_path.exists():
            try:
                tree = ET.parse(self.xml_path)
                root = tree.getroot()
                for view in root.findall('view'):
                    vid = view.get('id')
                    vcells = []
                    for btn in view.findall('button'):
                        x, y, w, h = int(btn.get('x', 0)), int(btn.get('y', 0)), int(btn.get('w', 0)), int(btn.get('h', 0))
                        k = btn.get('id', '')
                        if btn.get('icon'): self.icons[k] = btn.get('icon')
                        vcells.append((x, y, w, h, k))

                    grid = view.find('keygrid')
                    if grid is not None:
                        start_x = float(grid.get('start_x', 7))
                        y = float(grid.get('start_y', 66))
                        width = float(grid.get('width', 626))
                        for row in grid.findall('row'):
                            h = float(row.get('height', 50))
                            keys = row.findall('key')
                            weights = [float(k.get('weight', 1.0)) for k in keys]
                            total_weight = sum(weights) if weights else 1.0
                            unit = width / total_weight
                            x = start_x
                            for k, weight in zip(keys, weights):
                                w = unit * weight
                                key_id = k.get('id', '')
                                if k.get('icon'): self.icons[key_id] = k.get('icon')
                                vcells.append((x + 2, y + 2, w - 4, h - 4, key_id))
                                x += w
                            y += h
                    base_views[vid] = vcells
            except Exception as e:
                print(f'Default layout XML error ({self.xml_path}):', e, flush=True)

        # 2. Parse custom layout if present
        custom_cells = []
        if self.custom_xml_path and self.custom_xml_path.exists():
            try:
                tree = ET.parse(self.custom_xml_path)
                root = tree.getroot()
                # Accept <layout> or <whimpad> with <view>
                view_elem = root if root.tag in ('layout', 'view') else root.find('view')
                if view_elem is not None:
                    self.has_custom = True
                    self.custom_id = view_elem.get('id', 'custom')
                    self.custom_title = view_elem.get('label', view_elem.get('title', '게임 단축키'))
                    if view_elem.get('default', '').lower() in ('true', '1', 'yes'):
                        self.default_view = self.custom_id

                    # Absolute buttons
                    for btn in view_elem.findall('button'):
                        cell = self._parse_button(btn)
                        if cell: custom_cells.append(cell)

                    # Grid container
                    for grid in view_elem.findall('grid'):
                        gx = float(grid.get('x', 15))
                        gy = float(grid.get('y', 75))
                        gw = float(grid.get('w', 610))
                        gh = float(grid.get('h', 380))
                        rows = max(1, int(grid.get('rows', 1)))
                        cols = max(1, int(grid.get('cols', 1)))
                        gap = float(grid.get('gap', 6))

                        col_w = (gw - gap * (cols - 1)) / cols
                        row_h = (gh - gap * (rows - 1)) / rows
                        buttons = grid.findall('button')
                        for idx, btn in enumerate(buttons):
                            r_idx = idx // cols
                            c_idx = idx % cols
                            bx = gx + c_idx * (col_w + gap)
                            by = gy + r_idx * (row_h + gap)
                            cell = self._parse_button(btn, forced_rect=(bx, by, col_w, row_h))
                            if cell: custom_cells.append(cell)
            except Exception as e:
                print(f'Custom layout XML parse error ({self.custom_xml_path}), falling back:', e, flush=True)
                self.has_custom = False

        # 3. Construct dynamic header cells
        if self.has_custom:
            self.header_cells = [
                (337, 6, 54, 54, 'Pad'),
                (397, 6, 54, 54, 'Custom'),
                (457, 6, 54, 54, 'Keys'),
                (517, 6, 54, 54, 'Settings'),
                (577, 6, 54, 54, 'Sleep')
            ]
            self.icons['Custom'] = 'custom'
        else:
            self.header_cells = [
                (397, 6, 54, 54, 'Pad'),
                (457, 6, 54, 54, 'Keys'),
                (517, 6, 54, 54, 'Settings'),
                (577, 6, 54, 54, 'Sleep')
            ]

        self.icons['Pad'] = 'pad'
        self.icons['Keys'] = 'keys'
        self.icons['Settings'] = 'settings'
        self.icons['Sleep'] = 'sleep'

        # 4. Finalize view cell tuples with header prepended
        for vid, cells in base_views.items():
            self.views[vid] = tuple(self.header_cells + cells)

        if self.has_custom:
            self.views[self.custom_id] = tuple(self.header_cells + custom_cells)

    def _parse_button(self, btn, forced_rect=None):
        if forced_rect:
            x, y, w, h = forced_rect
        else:
            x = float(btn.get('x', 0))
            y = float(btn.get('y', 0))
            w = float(btn.get('w', 0))
            h = float(btn.get('h', 0))

        key_id = btn.get('id') or btn.get('key') or btn.get('combo') or btn.get('action') or btn.get('label', '')
        if not key_id:
            return None

        if btn.get('icon'): self.icons[key_id] = btn.get('icon')
        if btn.get('label'): self.labels[key_id] = btn.get('label')
        if btn.get('key'): self.actions[key_id] = f'key:{btn.get("key")}'
        elif btn.get('combo'): self.actions[key_id] = f'combo:{btn.get("combo")}'
        elif btn.get('action'): self.actions[key_id] = btn.get('action')

        return (x, y, w, h, key_id)

    def get_cells(self, mode):
        return self.views.get(mode, tuple(self.header_cells))

    def get_icon(self, key_id):
        return self.icons.get(key_id)

    def get_label(self, key_id):
        return self.labels.get(key_id)

    def get_action(self, key_id):
        return self.actions.get(key_id)
