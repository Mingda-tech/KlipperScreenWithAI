import logging
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel


def _translation_strings():
    _("First Layer")
    _("First Layer Detection")
    _("Foreign Object")
    _("Foreign Object Detection")
    _("General Detection")
    _("Spaghetti")
    _("Spaghetti Detection")
    _("Warp Edge")
    _("Warp Edge Detection")
    _("Warp Head")
    _("Warp Head Detection")


DETECTION_TYPES = [
    {
        "key": "spaghetti",
        "name": "Spaghetti Detection",
        "short_name": "Spaghetti",
        "macro": "AI_DETECT_SPAGHETTI",
        "default_threshold": 0.70,
        "default_interval": 30,
        "aliases": [],
    },
    {
        "key": "warphead",
        "name": "Warp Head Detection",
        "short_name": "Warp Head",
        "macro": "AI_DETECT_WARPHEAD",
        "default_threshold": 0.75,
        "default_interval": 60,
        "aliases": [],
    },
    {
        "key": "tooLessAndTooMuch",
        "name": "First Layer Detection",
        "short_name": "First Layer",
        "macro": "AI_DETECT_EXTRUSION",
        "default_threshold": 0.70,
        "default_interval": 60,
        "aliases": [
            "Extrusion Detection",
            "Extrusion",
            "First Layer Detection",
            "First Layer",
        ],
    },
    {
        "key": "warpEdgesAndNonStick",
        "name": "Warp Edge Detection",
        "short_name": "Warp Edge",
        "macro": "AI_DETECT_NONSTICK",
        "default_threshold": 0.70,
        "default_interval": 120,
        "aliases": [],
    },
    {
        "key": "foreignBody",
        "name": "Foreign Object Detection",
        "short_name": "Foreign Object",
        "macro": "AI_DETECT_FOREIGNBODY",
        "default_threshold": 0.60,
        "default_interval": 60,
        "aliases": ["Foreign Body Detection", "Foreign Body"],
    },
]

LEGACY_DETECTION_ALIASES = {
    "coco80": "General Detection",
    "ai_detect_coco80": "General Detection",
    "general detection": "General Detection",
    "general": "General Detection",
}


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.menu = ['main_menu']
        self.settings = {}
        self.status_timeout = None
        self.ai_online = False
        self.pause_on_defect = True
        self.last_result = None
        self._active = False

        self.labels['main_menu'] = self._build_main_page()
        self.labels['settings_menu'] = self._build_settings_page()

        self.content.add(self.labels['main_menu'])

    # ==================== UI Build ====================

    def _build_main_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        # --- Status bar ---
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        status_row.get_style_context().add_class("frame-item")

        self.labels['status_label'] = Gtk.Label()
        self._set_status_label(_("Checking..."), "gray")
        self.labels['status_label'].set_hexpand(True)
        self.labels['status_label'].set_halign(Gtk.Align.START)

        settings_btn = self._gtk.Button("fine-tune", _("Settings"), "color3")
        settings_btn.connect("clicked", self.load_menu, 'settings', _("Settings"))

        status_row.pack_start(self.labels['status_label'], True, True, 5)
        status_row.pack_end(settings_btn, False, False, 5)
        page.pack_start(status_row, False, False, 0)

        # --- Manual detection buttons (3 columns x 2 rows) ---
        detect_grid = self._gtk.HomogeneousGrid()
        button_styles = ["color1", "color2", "color3", "color1", "color2"]
        for idx, dt in enumerate(DETECTION_TYPES):
            key = dt["key"]
            btn = self._gtk.Button(None, _(dt["short_name"]), button_styles[idx])
            btn.connect("clicked", self.manual_detect, key)
            self.labels[f"btn_{key}"] = btn
            col, row = idx % 3, idx // 3
            detect_grid.attach(btn, col, row, 1, 1)
        page.pack_start(detect_grid, True, True, 0)

        # --- Pause on defect toggle ---
        pause_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        pause_row.get_style_context().add_class("frame-item")

        pause_label = Gtk.Label()
        pause_label.set_markup(
            f"<big><b>{GLib.markup_escape_text(_('Pause Print on Defect'))}</b></big>"
        )
        pause_label.set_hexpand(True)
        pause_label.set_halign(Gtk.Align.START)

        self.labels['pause_switch'] = Gtk.Switch()
        self.labels['pause_switch'].set_active(True)
        self.labels['pause_switch'].set_property("width-request", round(self._gtk.font_size * 7))
        self.labels['pause_switch'].set_property("height-request", round(self._gtk.font_size * 3.5))
        self.labels['pause_switch'].connect("notify::active", self.on_pause_toggled)

        pause_row.pack_start(pause_label, True, True, 5)
        pause_row.pack_end(self.labels['pause_switch'], False, False, 5)
        page.pack_start(pause_row, False, False, 0)

        # --- Latest detection result ---
        result_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        result_row.get_style_context().add_class("frame-item")

        result_title = Gtk.Label()
        result_title.set_markup(
            f"<big><b>{GLib.markup_escape_text(_('Latest Detection Result'))}</b></big>"
        )
        result_title.set_halign(Gtk.Align.START)

        self.labels['result_text'] = Gtk.Label()
        self.labels['result_text'].set_text(_("No detection results yet"))
        self.labels['result_text'].set_halign(Gtk.Align.START)
        self.labels['result_text'].set_line_wrap(True)
        self.labels['result_text'].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        result_row.pack_start(result_title, False, False, 2)
        result_row.pack_start(self.labels['result_text'], False, False, 2)
        page.pack_start(result_row, False, False, 0)

        return page

    def _build_settings_page(self):
        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        row_idx = 0

        for idx, dt in enumerate(DETECTION_TYPES):
            key = dt['key']

            # --- Section header ---
            header = Gtk.Label()
            header.set_markup(
                f"\n<big><b>{GLib.markup_escape_text(_(dt['name']))}</b></big>  <small>({key})</small>"
            )
            header.set_halign(Gtk.Align.START)
            grid.attach(header, 0, row_idx, 4, 1)
            row_idx += 1

            # --- Enable switch ---
            sw_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            sw_row.get_style_context().add_class("frame-item")

            en_label = Gtk.Label()
            en_label.set_markup(f"<b>{GLib.markup_escape_text(_('Enabled'))}</b>")
            self.labels[f'{key}_enabled'] = Gtk.Switch()
            self.labels[f'{key}_enabled'].set_active(True)
            self.labels[f'{key}_enabled'].set_property("width-request", round(self._gtk.font_size * 5))
            self.labels[f'{key}_enabled'].set_property("height-request", round(self._gtk.font_size * 3))

            sw_row.pack_start(en_label, False, False, 5)
            sw_row.pack_start(self.labels[f'{key}_enabled'], False, False, 5)

            grid.attach(sw_row, 0, row_idx, 4, 1)
            row_idx += 1

            # --- Confidence threshold slider ---
            conf_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            conf_label = Gtk.Label()
            conf_label.set_markup(f"<b>{GLib.markup_escape_text(_('Confidence'))}</b>")
            conf_label.set_size_request(round(self._gtk.font_size * 5), -1)

            self.labels[f'{key}_threshold'] = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0.1, 1.0, 0.05)
            self.labels[f'{key}_threshold'].set_value(dt['default_threshold'])
            self.labels[f'{key}_threshold'].set_digits(2)
            self.labels[f'{key}_threshold'].set_hexpand(True)
            self.labels[f'{key}_threshold'].set_has_origin(True)
            self.labels[f'{key}_threshold'].get_style_context().add_class("option_slider")

            conf_row.pack_start(conf_label, False, False, 5)
            conf_row.pack_start(self.labels[f'{key}_threshold'], True, True, 5)
            grid.attach(conf_row, 0, row_idx, 4, 1)
            row_idx += 1

            if idx < len(DETECTION_TYPES) - 1:
                separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
                grid.attach(separator, 0, row_idx, 4, 1)
                row_idx += 1

        # --- Save button ---
        save_btn = self._gtk.Button(None, _("Save"), "color1")
        save_btn.connect("clicked", self.save_settings)
        grid.attach(save_btn, 1, row_idx, 2, 1)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(grid)
        return scroll

    # ==================== Lifecycle ====================

    def activate(self):
        self._active = True
        self.fetch_status()
        self.fetch_settings()
        self.fetch_latest_result()
        self.status_timeout = GLib.timeout_add_seconds(30, self.fetch_status)

    def deactivate(self):
        self._active = False
        if self.status_timeout:
            GLib.source_remove(self.status_timeout)
            self.status_timeout = None

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False

    def process_update(self, action, data):
        if action == "notify_ai_detection_result":
            if isinstance(data, dict):
                self.last_result = data
                self._update_result_display()

    # ==================== REST API ====================

    def fetch_status(self):
        if not self._active:
            return False
        def _do():
            try:
                result = self._screen.apiclient.send_request("server/ai_detection/status")
            except Exception as e:
                logging.exception(f"AI detection: failed to fetch status: {e}")
                result = None
            GLib.idle_add(self._on_status_fetched, result)
        threading.Thread(target=_do, daemon=True).start()
        return self._active

    def _on_status_fetched(self, result):
        try:
            if result and isinstance(result, dict) and 'result' in result:
                data = result['result']
                if not isinstance(data, dict):
                    return
                self.ai_online = bool(data.get('service_available', False))
                color = "green" if self.ai_online else "red"
                text = _("Online") if self.ai_online else _("Offline")
                self._set_status_label(text, color)
                if 'pause_on_defect' in data:
                    self._set_pause_switch(bool(data['pause_on_defect']))
                if 'last_detection' in data and isinstance(data['last_detection'], dict):
                    self.last_result = data['last_detection']
                    self._update_result_display()
            else:
                self.ai_online = False
                self._set_status_label(_("Unknown"), "gray")
        except Exception as e:
            logging.exception(f"AI detection: error updating status UI: {e}")

    def fetch_settings(self):
        def _do():
            try:
                result = self._screen.apiclient.send_request("server/ai_detection/settings")
            except Exception as e:
                logging.exception(f"AI detection: failed to fetch settings: {e}")
                result = None
            GLib.idle_add(self._on_settings_fetched, result)
        threading.Thread(target=_do, daemon=True).start()

    def _on_settings_fetched(self, result):
        try:
            if not result or not isinstance(result, dict) or 'result' not in result:
                return
            data = result['result']
            if not isinstance(data, dict):
                return
            categories = data.get('categories', {})
            if not isinstance(categories, dict):
                return
            self.settings = categories

            if 'pause_on_defect' in data:
                self._set_pause_switch(bool(data['pause_on_defect']))

            for dt in DETECTION_TYPES:
                key = dt['key']
                if key not in categories:
                    continue
                cat = categories[key]
                if not isinstance(cat, dict):
                    continue
                if f'{key}_enabled' in self.labels:
                    self.labels[f'{key}_enabled'].set_active(bool(cat.get('enabled', True)))
                if f'{key}_threshold' in self.labels:
                    try:
                        val = float(cat.get('confidence_threshold', dt['default_threshold']))
                        self.labels[f'{key}_threshold'].set_value(max(0.1, min(1.0, val)))
                    except (TypeError, ValueError):
                        pass
        except Exception as e:
            logging.exception(f"AI detection: error updating settings UI: {e}")

    def fetch_latest_result(self):
        def _do():
            try:
                result = self._screen.apiclient.send_request("server/ai_detection/history?limit=1")
            except Exception as e:
                logging.exception(f"AI detection: failed to fetch history: {e}")
                result = None
            GLib.idle_add(self._on_history_fetched, result)
        threading.Thread(target=_do, daemon=True).start()

    def _on_history_fetched(self, result):
        try:
            if not result or not isinstance(result, dict) or 'result' not in result:
                return
            data = result['result']
            if not isinstance(data, dict):
                return
            records = data.get('records', [])
            if isinstance(records, list) and records:
                self.last_result = records[0]
                self._update_result_display()
        except Exception as e:
            logging.exception(f"AI detection: error updating history UI: {e}")

    def _update_result_display(self):
        if not self.last_result or not isinstance(self.last_result, dict):
            self.labels['result_text'].set_text(_("No detection results yet"))
            return
        r = self.last_result

        dtype = self._translate_detection_name(r.get('model_name', r.get('defect_type')))
        defect = bool(r.get('has_defect', False))
        status_label = _("Defect") if defect else _("Normal")
        status_color = "red" if defect else "green"
        escaped_type = GLib.markup_escape_text(dtype)
        status = f'<span foreground="{status_color}">{GLib.markup_escape_text(status_label)}</span>'
        self.labels['result_text'].set_markup(f"<b>{escaped_type}</b>\n{status}")

    # ==================== User Actions ====================

    def manual_detect(self, widget, defect_type):
        if not self.ai_online:
            self._screen.show_popup_message(_("AI service offline. Detection unavailable."), level=2)
            return

        dt_info = next((d for d in DETECTION_TYPES if d['key'] == defect_type), None)
        if not dt_info:
            logging.error(f"AI detection: unknown defect type: {defect_type}")
            return
        if not self._is_detection_enabled(defect_type):
            self._screen.show_popup_message(
                _("'%s' is disabled in AI detection settings. Please enable it first.") % _(dt_info['name']),
                level=2,
            )
            return
        macro = dt_info['macro']
        if macro not in self._printer.get_gcode_macros():
            logging.warning(f"AI detection: macro not found: {macro}")
            self._screen.show_popup_message(
                _("Macro %s is undefined. Please check whether ai_setting.cfg is loaded.") % macro,
                level=2,
            )
            return
        self._screen._ws.klippy.gcode_script(macro)
        self._screen.show_popup_message(_("%s triggered.") % _(dt_info['name']), level=1)

    def on_pause_toggled(self, switch, gparam):
        active = switch.get_active()

        def _do():
            try:
                self._screen.apiclient.post_request(
                    "server/ai_detection/settings",
                    json={"pause_on_defect": active})
            except Exception as e:
                logging.exception(f"AI detection: failed to update pause_on_defect: {e}")
        threading.Thread(target=_do, daemon=True).start()

    def save_settings(self, widget):
        categories = {}
        for dt in DETECTION_TYPES:
            key = dt['key']
            existing = self.settings.get(key, {})
            if not isinstance(existing, dict):
                existing = {}
            try:
                detection_interval = int(existing.get('detection_interval', dt['default_interval']))
            except (TypeError, ValueError):
                detection_interval = dt['default_interval']
            category = {
                "enabled": self.labels[f'{key}_enabled'].get_active(),
                "confidence_threshold": round(self.labels[f'{key}_threshold'].get_value(), 2),
                "scheduled": bool(existing.get('scheduled', False)),
                "detection_interval": max(10, min(300, detection_interval)),
            }
            categories[key] = category

        def _do():
            try:
                result = self._screen.apiclient.post_request(
                    "server/ai_detection/settings",
                    json={"categories": categories})
                if result:
                    GLib.idle_add(self._set_detection_settings, categories)
                    GLib.idle_add(self._screen.show_popup_message, _("Saved"), 1)
                else:
                    GLib.idle_add(self._screen.show_popup_message, _("Error"), 2)
            except Exception as e:
                logging.exception(f"AI detection: failed to save settings: {e}")
                GLib.idle_add(self._screen.show_popup_message, _("Error"), 2)
        threading.Thread(target=_do, daemon=True).start()

    # ==================== Helpers ====================

    def _set_status_label(self, text, color):
        self.labels['status_label'].set_markup(
            f'<big><b>{GLib.markup_escape_text(_("AI Status"))}:</b> '
            f'<span foreground="{color}">● {GLib.markup_escape_text(text)}</span></big>'
        )

    def _is_detection_enabled(self, defect_type):
        category = self.settings.get(defect_type)
        if isinstance(category, dict) and 'enabled' in category:
            return bool(category.get('enabled'))
        return True

    def _set_detection_settings(self, categories):
        if isinstance(categories, dict):
            self.settings = categories

    def _translate_detection_name(self, raw_name):
        if raw_name is None:
            return _("Unknown")

        value = str(raw_name)
        normalized = value.strip().casefold()
        for dt in DETECTION_TYPES:
            aliases = [
                dt["key"],
                dt["macro"],
                dt["name"],
                dt["short_name"],
                *dt.get("aliases", []),
            ]
            if normalized in {alias.casefold() for alias in aliases}:
                return _(dt["name"])
        if normalized in LEGACY_DETECTION_ALIASES:
            return _(LEGACY_DETECTION_ALIASES[normalized])
        return value

    def _set_pause_switch(self, active):
        self.pause_on_defect = active
        try:
            self.labels['pause_switch'].handler_block_by_func(self.on_pause_toggled)
            self.labels['pause_switch'].set_active(active)
            self.labels['pause_switch'].handler_unblock_by_func(self.on_pause_toggled)
        except Exception as e:
            logging.warning(f"AI detection: failed to update pause switch: {e}")
