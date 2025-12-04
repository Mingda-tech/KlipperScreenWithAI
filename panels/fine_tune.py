import logging
import re
import gi
import subprocess
import mpv
from contextlib import suppress

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
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
        self.mpv = None
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

        self.labels['z+'] = self._gtk.Button("bed_down", "Z+", "color1")
        self.labels['z-'] = self._gtk.Button("bed_up", "Z-", "color1")
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
            grid.attach(self.labels['z+'], 0, 0, 1, 1)
            grid.attach(self.labels['z-'], 1, 0, 1, 1)
            grid.attach(self.labels['zoffset'], 2, 0, 1, 1)
            grid.attach(zgrid, 0, 1, 3, 1)
            grid.attach(self.labels['speed-'], 0, 2, 1, 1)
            grid.attach(self.labels['speed+'], 1, 2, 1, 1)
            grid.attach(self.labels['speedfactor'], 2, 2, 1, 1)
            grid.attach(spdgrid, 0, 3, 3, 1)
            grid.attach(self.labels['extrude-'], 0, 4, 1, 1)
            grid.attach(self.labels['extrude+'], 1, 4, 1, 1)
            grid.attach(self.labels['extrudefactor'], 2, 4, 1, 1)
            grid.attach(extgrid, 0, 5, 3, 1)
        else:
            # 添加摄像头支持
            camera_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            for i, cam in enumerate(self._printer.cameras):
                if not cam["enabled"] or (cam["name"] != 'webcaml' and cam["name"] != 'webcamr'):
                # if not cam["enabled"] or cam["name"] != 'webcam':
                    continue
                logging.info(cam)
                cam[cam["name"]] = self._gtk.Button(
                    image_name="camera", label=_("Start"), style=f"color{i % 4 + 1}",
                    scale=self.bts, position=Gtk.PositionType.LEFT, lines=1
                )
                cam[cam["name"]].set_hexpand(True)
                cam[cam["name"]].set_vexpand(True)
                cam[cam["name"]].connect("clicked", self.play, cam)
                camera_box.add(cam[cam["name"]])

            self.scroll = self._gtk.ScrolledWindow()
            self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            self.scroll.add(camera_box)
            
            # 设置摄像头占40% (2/5)，操作区域占60% (3/5)
            self.scroll.set_size_request(int(self._screen.width * 0.4), -1)
            grid.set_column_homogeneous(False)
            
            grid.attach(self.scroll, 0, 0, 1, 4)  # 摄像头占据左侧
            grid.attach(self.labels['zoffset'], 1, 0, 1, 1)
            grid.attach(self.labels['z-'], 1, 1, 1, 1)
            grid.attach(self.labels['z+'], 1, 2, 1, 1)
            grid.attach(zgrid, 1, 3, 1, 1)
            grid.attach(self.labels['speedfactor'], 2, 0, 1, 1)
            grid.attach(self.labels['speed+'], 2, 1, 1, 1)
            grid.attach(self.labels['speed-'], 2, 2, 1, 1)
            grid.attach(spdgrid, 2, 3, 1, 1)
            grid.attach(self.labels['extrudefactor'], 3, 0, 1, 1)
            grid.attach(self.labels['extrude+'], 3, 1, 1, 1)
            grid.attach(self.labels['extrude-'], 3, 2, 1, 1)
            grid.attach(extgrid, 3, 3, 1, 1)

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
                if abs(self._screen.manual_settings[self.current_extruder]["zoffset"]) < 10:
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

    def play(self, widget, cam):
        url = cam['stream_url']
        if url.startswith('/'):
            logging.info("camera URL is relative")
            endpoint = self._screen.apiclient.endpoint.split(':')
            url = f"{endpoint[0]}:{endpoint[1]}{url}"
        vf = ""
        if cam["flip_horizontal"]:
            vf += "hflip,"
        if cam["flip_vertical"]:
            vf += "vflip,"
        vf += f"rotate:{cam['rotation']*3.14159/180}"
        logging.info(f"video filters: {vf}")

        if check_web_page_access(url) == False:
            self._screen.show_popup_message(_("Please wait for the camera initialization to complete."), level=1)
            return

        if self.mpv:
            self.mpv.terminate()
        
        self.mpv = mpv.MPV(fullscreen=True, log_handler=self.log, vo='gpu,wlshm,xv,x11', wid=str(widget.get_property("window").get_xid()))
        self.mpv.vf = vf

        with suppress(Exception):
            self.mpv.profile = 'sw-fast'

        # LOW LATENCY PLAYBACK
        with suppress(Exception):
            self.mpv.profile = 'low-latency'
        self.mpv.untimed = True
        self.mpv.audio = 'no'

        logging.debug(f"Camera URL: {url}")
        self.mpv.loop = True
        self.mpv.play(url)

        try:
            self.mpv.wait_until_playing()
        except mpv.ShutdownError:
            logging.info('Exiting Fullscreen')
            return
        except Exception as e:
            logging.exception(e)
            return

    def log(self, loglevel, component, message):
        logging.debug(f'[{loglevel}] {component}: {message}')
        if loglevel == 'error' and 'No Xvideo support found' not in message:
            self._screen.show_popup_message(f'{message}')

    def deactivate(self):
        if self.mpv:
            self.mpv.terminate()
            self.mpv = None


def check_web_page_access(url):
    try:
        result = subprocess.run(["curl", "-I", url], check=True, capture_output=True, text=True, timeout=10)
        status_code = result.stdout.splitlines()[0].split()[1]
        if status_code == "200":
            logging.info(f"The web page at {url} is accessible. Status code: {status_code}")
            return True
        else:
            logging.warning(f"Warning: The web page at {url} returned status code {status_code}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error: The web page at {url} is not accessible. {e}")
    except subprocess.TimeoutExpired:
        logging.error(f"Error: Timeout occurred while checking the web page at {url}.")
    return False
