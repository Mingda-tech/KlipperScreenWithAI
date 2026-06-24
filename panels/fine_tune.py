import logging
import re
import gi
import urllib.request

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    toolhead_camera_names = ("l_toolheadcam", "r_toolheadcam", "toolheadcam")
    z_deltas = ["0.02", "0.1"]
    z_delta = z_deltas[-1]
    speed_deltas = ['5', '25']
    s_delta = speed_deltas[-1]
    extrude_deltas = ['1', '2']
    e_delta = extrude_deltas[-1]
    speed = extrusion = 100
    z_offset = 0.0
    previous_extruder = ''
    extruder_target = 0

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.camera_timeout = None
        self.current_cam = None
        self.cameras = self.get_toolhead_cameras()
        self.camera_frame = None
        self.camera_image = None
        if self.cameras:
            self.camera_frame = Gtk.Frame()
            self.camera_image = Gtk.Image()
            self.camera_frame.add(self.camera_image)
            self.camera_frame.set_hexpand(True)
            self.camera_frame.set_vexpand(True)

        if self.ks_printer_cfg is not None:
            bs = self.ks_printer_cfg.get("z_babystep_values", "0.02, 0.1")
            if re.match(r'^[0-9,\.\s]+$', bs):
                bs = [str(i.strip()) for i in bs.split(',')]
                if 1 < len(bs) < 3:
                    self.z_deltas = bs
                    self.z_delta = self.z_deltas[-1]

        zgrid = Gtk.Grid()
        for j, i in enumerate(self.z_deltas):
            self.labels[f"zdelta{i}"] = self._gtk.Button(label=i)
            self.labels[f"zdelta{i}"].connect("clicked", self.change_percent_delta, "z_offset", float(i))
            ctx = self.labels[f"zdelta{i}"].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.z_deltas) - 1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.z_delta:
                ctx.add_class("distbutton_active")
            zgrid.attach(self.labels[f"zdelta{i}"], j, 0, 1, 1)

        spdgrid = Gtk.Grid()
        for j, i in enumerate(self.speed_deltas):
            self.labels[f"sdelta{i}"] = self._gtk.Button(label=f"{i}%")
            self.labels[f"sdelta{i}"].connect("clicked", self.change_percent_delta, "speed", int(i))
            ctx = self.labels[f"sdelta{i}"].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.speed_deltas) - 1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.s_delta:
                ctx.add_class("distbutton_active")
            spdgrid.attach(self.labels[f"sdelta{i}"], j, 0, 1, 1)

        extgrid = Gtk.Grid()
        for j, i in enumerate(self.extrude_deltas):
            self.labels[f"edelta{i}"] = self._gtk.Button(label=f"{i}%")
            self.labels[f"edelta{i}"].connect("clicked", self.change_percent_delta, "extrude", int(i))
            ctx = self.labels[f"edelta{i}"].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.extrude_deltas) - 1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.e_delta:
                ctx.add_class("distbutton_active")
            extgrid.attach(self.labels[f"edelta{i}"], j, 0, 1, 1)
        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)

        if self._printer.use_bed_move():
            z_up_image = "bed_down"
            z_down_image = "bed_up"
            z_up_label = _("Lower")
            z_down_label = _("Raise")
        else:
            z_up_image = "z-farther"
            z_down_image = "z-closer"
            z_up_label = "Z+"
            z_down_label = "Z-"
        self.labels['z+'] = self._gtk.Button(z_up_image, z_up_label, "color1")
        self.labels['z-'] = self._gtk.Button(z_down_image, z_down_label, "color1")
        self.labels['zoffset'] = self._gtk.Button("refresh", '  0.00' + _("mm"),
                                                  "color1", self.bts, Gtk.PositionType.LEFT, 1)
        self.labels['speed+'] = self._gtk.Button("speed+", _("Speed +"), "color3")
        self.labels['speed-'] = self._gtk.Button("speed-", _("Speed -"), "color3")
        self.labels['speedfactor'] = self._gtk.Button("refresh", "  100%",
                                                      "color3", self.bts, Gtk.PositionType.LEFT, 1)

        self.labels['extrude+'] = self._gtk.Button("flow+", _("Flow +"), "color4")
        self.labels['extrude-'] = self._gtk.Button("flow-", _("Flow -"), "color4")
        self.labels['extrudefactor'] = self._gtk.Button("refresh", "  100%",
                                                        "color4", self.bts, Gtk.PositionType.LEFT, 1)
        if self._screen.vertical_mode:
            row_offset = 0
            if self.camera_frame:
                grid.attach(self.camera_frame, 0, 0, 3, 2)
                row_offset = 2
            grid.attach(self.labels['z+'], 0, row_offset, 1, 1)
            grid.attach(self.labels['z-'], 1, row_offset, 1, 1)
            grid.attach(self.labels['zoffset'], 2, row_offset, 1, 1)
            grid.attach(zgrid, 0, row_offset + 1, 3, 1)
            grid.attach(self.labels['speed-'], 0, row_offset + 2, 1, 1)
            grid.attach(self.labels['speed+'], 1, row_offset + 2, 1, 1)
            grid.attach(self.labels['speedfactor'], 2, row_offset + 2, 1, 1)
            grid.attach(spdgrid, 0, row_offset + 3, 3, 1)
            grid.attach(self.labels['extrude-'], 0, row_offset + 4, 1, 1)
            grid.attach(self.labels['extrude+'], 1, row_offset + 4, 1, 1)
            grid.attach(self.labels['extrudefactor'], 2, row_offset + 4, 1, 1)
            grid.attach(extgrid, 0, row_offset + 5, 3, 1)
        else:
            if self.camera_frame:
                grid.set_column_homogeneous(False)
                grid.attach(self.camera_frame, 0, 0, 2, 4)
                z_col = 2
                speed_col = 3
                extrude_col = 4
            else:
                z_col = 0
                speed_col = 1
                extrude_col = 2
            grid.attach(self.labels['zoffset'], z_col, 0, 1, 1)
            if self._printer.use_bed_move():
                grid.attach(self.labels['z-'], z_col, 1, 1, 1)
                grid.attach(self.labels['z+'], z_col, 2, 1, 1)
            else:
                grid.attach(self.labels['z+'], z_col, 1, 1, 1)
                grid.attach(self.labels['z-'], z_col, 2, 1, 1)
            grid.attach(zgrid, z_col, 3, 1, 1)
            grid.attach(self.labels['speedfactor'], speed_col, 0, 1, 1)
            grid.attach(self.labels['speed+'], speed_col, 1, 1, 1)
            grid.attach(self.labels['speed-'], speed_col, 2, 1, 1)
            grid.attach(spdgrid, speed_col, 3, 1, 1)
            grid.attach(self.labels['extrudefactor'], extrude_col, 0, 1, 1)
            grid.attach(self.labels['extrude+'], extrude_col, 1, 1, 1)
            grid.attach(self.labels['extrude-'], extrude_col, 2, 1, 1)
            grid.attach(extgrid, extrude_col, 3, 1, 1)

        self.labels['z+'].connect("clicked", self.change_babystepping, "+")
        self.labels['zoffset'].connect("clicked", self.change_babystepping, "reset")
        self.labels['z-'].connect("clicked", self.change_babystepping, "-")
        self.labels['speed+'].connect("clicked", self.change_speed, "+")
        self.labels['speedfactor'].connect("clicked", self.change_speed, "reset")
        self.labels['speed-'].connect("clicked", self.change_speed, "-")
        self.labels['extrude+'].connect("clicked", self.change_extrusion, "+")
        self.labels['extrudefactor'].connect("clicked", self.change_extrusion, "reset")
        self.labels['extrude-'].connect("clicked", self.change_extrusion, "-")
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        self.update_camera_for_extruder()
        self.content.add(grid)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        if "gcode_move" in data:
            if "homing_origin" in data["gcode_move"]:
                self.labels['zoffset'].set_label(f'  {data["gcode_move"]["homing_origin"][2]:.3f}mm')
                self.z_offset = float(data["gcode_move"]["homing_origin"][2])
            if "extrude_factor" in data["gcode_move"]:
                self.extrusion = round(float(data["gcode_move"]["extrude_factor"]) * 100)
                self.labels['extrudefactor'].set_label(f"  {self.extrusion:3}%")
            if "speed_factor" in data["gcode_move"]:
                self.speed = round(float(data["gcode_move"]["speed_factor"]) * 100)
                self.labels['speedfactor'].set_label(f"  {self.speed:3}%")

        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        self.update_camera_for_extruder()
        for x in self._printer.get_temp_devices():
            if x in data and x == self.current_extruder:
                self.extruder_target = self._printer.get_dev_stat(x, "target")
                    
        if self._screen.manual_settings:
            extruder_temp = int(self._screen.manual_settings[self.current_extruder]["extruder_temp"])
            # logging.info(f"Setting temperature to {self._screen.manual_settings[self.current_extruder]['extruder_temp']}, {self.current_extruder} +++++++222222")
            if self.previous_extruder == self.current_extruder and self.extruder_target > 150 and extruder_temp > 150 and abs(extruder_temp - self.extruder_target) > 0.0001 :
                self._screen._ws.klippy.gcode_script(f"M104 S{extruder_temp}")
                # logging.info(f"Setting temperature to {self._screen.manual_settings[self.current_extruder]['extruder_temp']}, {self.current_extruder}")
            
            if self.previous_extruder != self.current_extruder:
                # logging.info(f"Setting extruder speedfactor to {self._screen.manual_settings[self.current_extruder]['speedfactor']}, {self.current_extruder}")
                if self._screen.manual_settings[self.current_extruder]["speedfactor"] > 1:
                    self._screen._ws.klippy.gcode_script(f"M220 S{self._screen.manual_settings[self.current_extruder]['speedfactor']}")
                    logging.info(f"Setting speedfactor to {self._screen.manual_settings[self.current_extruder]['speedfactor']}, {self.current_extruder}")
                
                # logging.info(f"Setting extrudefactor to {self._screen.manual_settings[self.current_extruder]['extrudefactor']}, {self.current_extruder}")
                if self._screen.manual_settings[self.current_extruder]["extrudefactor"] > 1:
                    self._screen._ws.klippy.gcode_script(f"M221 S{self._screen.manual_settings[self.current_extruder]['extrudefactor']}")
                    logging.info(f"Setting extrudefactor to {self._screen.manual_settings[self.current_extruder]['extrudefactor']}, {self.current_extruder}")
                
                # logging.info(f"Setting zoffset to {self._screen.manual_settings[self.current_extruder]['zoffset']}, {self.current_extruder}")
                if 0.001 < abs(self._screen.manual_settings[self.current_extruder]["zoffset"]) < 10:
                    self._screen._ws.klippy.gcode_script(f"SET_GCODE_OFFSET Z={self._screen.manual_settings[self.current_extruder]['zoffset']} MOVE=1")
                    logging.info(f"Setting zoffset to {self._screen.manual_settings[self.current_extruder]['zoffset']}, {self.current_extruder}")
                self.previous_extruder = self.current_extruder
    def change_babystepping(self, widget, direction):
        if direction == "reset":
            self.labels['zoffset'].set_label('  0.00mm')
            self._screen._send_action(widget, "printer.gcode.script", {"script": "SET_GCODE_OFFSET Z=0 MOVE=1"})
            return
        elif direction == "+":
            self.z_offset += float(self.z_delta)
        elif direction == "-":
            self.z_offset -= float(self.z_delta)
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        self._screen.manual_settings[current_extruder]["zoffset"] = self.z_offset
        self.labels['zoffset'].set_label(f'  {self.z_offset:.3f}mm')
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"SET_GCODE_OFFSET Z_ADJUST={direction}{self.z_delta} MOVE=1"})

    def change_extrusion(self, widget, direction):
        if direction == "+":
            self.extrusion += int(self.e_delta)
        elif direction == "-":
            self.extrusion -= int(self.e_delta)
        elif direction == "reset":
            self.extrusion = 100
        self.extrusion = max(self.extrusion, 1)
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        self._screen.manual_settings[current_extruder]["extrudefactor"] = self.extrusion  
        self.labels['extrudefactor'].set_label(f"  {self.extrusion:3}%")
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": KlippyGcodes.set_extrusion_rate(self.extrusion)})

    def change_speed(self, widget, direction):
        if direction == "+":
            self.speed += int(self.s_delta)
        elif direction == "-":
            self.speed -= int(self.s_delta)
        elif direction == "reset":
            self.speed = 100

        self.speed = max(self.speed, 5)
        self.labels['speedfactor'].set_label(f"  {self.speed:3}%")
        current_extruder = self._printer.get_stat("toolhead", "extruder")
        self._screen.manual_settings[current_extruder]["speedfactor"] = self.speed
        self._screen._send_action(widget, "printer.gcode.script", {"script": KlippyGcodes.set_speed_rate(self.speed)})

    def change_percent_delta(self, widget, array, delta):
        logging.info(f"### Delta {delta}")
        widget.get_style_context().add_class("distbutton_active")
        if array == "z_offset":
            self.labels[f"zdelta{self.z_delta}"].get_style_context().remove_class("distbutton_active")
            self.z_delta = delta
        elif array == "speed":
            self.labels[f"sdelta{self.s_delta}"].get_style_context().remove_class("distbutton_active")
            self.s_delta = delta
        elif array == "extrude":
            self.labels[f"edelta{self.e_delta}"].get_style_context().remove_class("distbutton_active")
            self.e_delta = delta

    def get_toolhead_cameras(self):
        cameras = {}
        for cam in self._printer.cameras:
            name = cam.get("name")
            if cam.get("enabled") and name in self.toolhead_camera_names:
                cameras[name] = cam
                logging.debug(f"Found toolhead camera: {name}")
        return cameras

    def get_snapshot_url(self, cam):
        url = cam.get('snapshot_url', cam.get('stream_url', ''))
        if not url:
            return None
        if url.startswith('/'):
            endpoint = self._screen.apiclient.endpoint.split(':')
            url = f"{endpoint[0]}:{endpoint[1]}{url}"
        return url

    def update_camera_for_extruder(self):
        if not self.cameras:
            return

        try:
            tool_number = self._printer.get_tool_number(self.current_extruder)
        except ValueError:
            tool_number = 0

        cam_name = "l_toolheadcam" if tool_number == 0 else "r_toolheadcam"
        new_cam = self.cameras.get(cam_name) or self.cameras.get("toolheadcam")
        if new_cam is None and len(self.cameras) == 1:
            new_cam = next(iter(self.cameras.values()))
        if new_cam and new_cam != self.current_cam:
            self.current_cam = new_cam
            logging.debug(f"Switched to camera: {new_cam['name']} for {self.current_extruder}")

    def start_camera(self):
        if self.current_cam and self.camera_timeout is None:
            logging.debug(f"Starting camera: {self.current_cam['name']}")
            self.update_camera_image()

    def stop_camera(self):
        if self.camera_timeout:
            GLib.source_remove(self.camera_timeout)
            self.camera_timeout = None
        logging.debug("Camera stopped")

    def update_camera_image(self):
        self.camera_timeout = None
        if self.current_cam is None or self.camera_image is None:
            return False

        url = self.get_snapshot_url(self.current_cam)
        if not url:
            logging.error("No snapshot URL available")
            return False

        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                data = response.read()

            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pixbuf = loader.get_pixbuf()

            if pixbuf:
                rotation = self.current_cam.get('rotation', 0)
                if rotation == 90:
                    pixbuf = pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.CLOCKWISE)
                elif rotation == 180:
                    pixbuf = pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.UPSIDEDOWN)
                elif rotation == 270:
                    pixbuf = pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.COUNTERCLOCKWISE)

                if self.current_cam.get('flip_horizontal', False):
                    pixbuf = pixbuf.flip(True)
                if self.current_cam.get('flip_vertical', False):
                    pixbuf = pixbuf.flip(False)

                if self._screen.vertical_mode:
                    max_width = self._gtk.content_width
                    max_height = max(1, self._gtk.content_height // 3)
                else:
                    max_width = max(1, self._gtk.content_width * 2 // 5)
                    max_height = max(1, self._gtk.content_height)

                img_width = pixbuf.get_width()
                img_height = pixbuf.get_height()
                if img_width > 0 and img_height > 0:
                    scale = max(max_width / img_width, max_height / img_height)
                    new_width = int(img_width * scale)
                    new_height = int(img_height * scale)

                    if new_width > 0 and new_height > 0:
                        pixbuf = pixbuf.scale_simple(new_width, new_height, GdkPixbuf.InterpType.BILINEAR)

                        if new_width > max_width or new_height > max_height:
                            crop_x = max(0, (new_width - max_width) // 2)
                            crop_y = max(0, (new_height - max_height) // 2)
                            crop_w = min(max_width, new_width)
                            crop_h = min(max_height, new_height)
                            try:
                                pixbuf = pixbuf.new_subpixbuf(crop_x, crop_y, crop_w, crop_h)
                            except Exception as e:
                                logging.warning(f"Crop failed: {e}")

                self.camera_image.set_from_pixbuf(pixbuf)

        except Exception as e:
            logging.warning(f"Failed to update camera image: {e}")

        self.camera_timeout = GLib.timeout_add(100, self.update_camera_image)
        return False

    def activate(self):
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        self.update_camera_for_extruder()
        self.start_camera()

    def deactivate(self):
        self.stop_camera()
