import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.leds = [
            led for led in self._printer.get_leds()
            if not self.led_name(led).startswith("_")
        ]
        self.scales = {}

        self.grid = Gtk.Grid()
        self.grid.set_hexpand(True)
        self.grid.set_vexpand(False)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.grid)
        self.content.add(scroll)

        self.load_leds()

    @staticmethod
    def led_name(led):
        return led.split()[1] if len(led.split()) > 1 else led

    def load_leds(self):
        if not self.leds:
            self.grid.attach(Gtk.Label(label=_("No info available"), vexpand=True), 0, 0, 1, 1)
            return

        for row, led in enumerate(self.leds):
            name = Gtk.Label()
            name.set_markup(f"<big><b>{self.prettify(self.led_name(led))}</b></big>")
            name.set_hexpand(True)
            name.set_halign(Gtk.Align.START)
            name.set_valign(Gtk.Align.CENTER)
            name.set_line_wrap(True)
            name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

            off = self._gtk.Button("cancel", _("Turn off"), "color1", self.bts, Gtk.PositionType.LEFT, 1)
            off.set_hexpand(False)
            off.connect("clicked", self.set_brightness, led, 0)

            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            scale.set_value(round(self.get_brightness(led) * 100))
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            scale.connect("button-release-event", self.apply_scale, led)
            self.scales[led] = scale

            full = self._gtk.Button("light", _("Brightest"), "color2", self.bts, Gtk.PositionType.LEFT, 1)
            full.set_hexpand(False)
            full.connect("clicked", self.set_brightness, led, 1)

            item = Gtk.Grid()
            item.get_style_context().add_class("frame-item")
            item.set_hexpand(True)
            item.set_vexpand(False)
            item.attach(name, 0, 0, 3, 1)
            item.attach(off, 0, 1, 1, 1)
            item.attach(scale, 1, 1, 1, 1)
            item.attach(full, 2, 1, 1, 1)
            self.grid.attach(item, 0, row, 1, 1)

        self.grid.show_all()

    def get_led_color_order(self, led):
        color_order = self._printer.get_led_color_order(led)
        if color_order is None:
            logging.error(f"Error getting color order for {led}")
            return ""
        return color_order

    def get_brightness_index(self, led):
        color_order = self.get_led_color_order(led)
        if "W" in color_order:
            return 3
        for idx, channel in enumerate(("R", "G", "B")):
            if channel in color_order:
                return idx
        return 3

    def get_current_color_data(self, led):
        color_data = self._printer.get_stat(led, "color_data")
        if isinstance(color_data, list) and color_data:
            color = list(color_data[0])
            return (color + [0, 0, 0, 0])[:4]
        return [0, 0, 0, 0]

    def get_brightness(self, led):
        color = self.get_current_color_data(led)
        return color[self.get_brightness_index(led)]

    def brightness_to_color(self, led, brightness):
        color_order = self.get_led_color_order(led)
        color = [0, 0, 0, 0]
        if "W" in color_order:
            color[3] = brightness
            return color
        for idx, channel in enumerate(("R", "G", "B")):
            if channel in color_order:
                color[idx] = brightness
        return color

    def process_update(self, action, data):
        if action != 'notify_status_update':
            return
        for led in self.scales:
            if led in data and "color_data" in data[led]:
                color = list(data[led]["color_data"][0])
                color = (color + [0, 0, 0, 0])[:4]
                self.scales[led].set_value(round(color[self.get_brightness_index(led)] * 100))

    def apply_scale(self, widget, event, led):
        self.set_led_color(led, widget.get_value() / 100)

    def set_brightness(self, widget, led, brightness):
        if led in self.scales:
            self.scales[led].set_value(brightness * 100)
        self.set_led_color(led, brightness)

    def set_led_color(self, led, brightness):
        name = self.led_name(led)
        color = self.brightness_to_color(led, brightness)
        self._screen._send_action(None, "printer.gcode.script",
                                  {"script": KlippyGcodes.set_led_color(name, color)})
