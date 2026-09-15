#!/usr/bin/env python3
"""BoAYO desktop backed entirely by BOSIO Window Manager windows."""
from __future__ import annotations
import math, signal, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bosio_wm_client import BosioWMClient
from boayo_shell import BoayoLauncherShell
from bosio_window_manager import _direction, _basis


def launcher_point_at_gaze(shell, panel_az, panel_el, yaw, pitch):
    """Return launcher surface pixels, or None outside its BOSIO allocation."""
    direction = _direction(yaw, pitch)
    center, right, up = _basis(panel_az, panel_el)
    dot = float(direction @ center)
    if dot <= 0:
        return None
    x = float(direction @ right) / dot / math.tan(math.radians(21.0))
    y = float(direction @ up) / dot / math.tan(math.radians(15.0))
    if abs(x) > 1 or abs(y) > 1:
        return None
    return (x + 1) * .5 * shell.width, (1 - y) * .5 * shell.height


def launcher_contains_point(shell, x, y):
    """The visible panel excludes the black margin of its BOSIO window."""
    rect = shell.window
    if not (rect.x <= x <= rect.x + rect.width and
            rect.y <= y <= rect.y + rect.height):
        return False
    radius = 18.0  # BoayoLauncherShell.render() draws this rounded rectangle.
    dx = max(rect.x + radius - x, 0, x - (rect.x + rect.width - radius))
    dy = max(rect.y + radius - y, 0, y - (rect.y + rect.height - radius))
    return dx * dx + dy * dy <= radius * radius


def launcher_contains_gaze(shell, panel_az, panel_el, yaw, pitch):
    point = launcher_point_at_gaze(shell, panel_az, panel_el, yaw, pitch)
    return point is not None and launcher_contains_point(shell, *point)


def hide_launcher(wm, shell, wid, reason):
    wm.configure_window(wid, mapped=False)
    shell.visible = False
    print(f"BOAYO_PANEL_HIDDEN {reason}", flush=True)


def click_launcher_at_gaze(wm, shell, wid, panel_az, panel_el, yaw, pitch):
    """Run the pointed JSON app and remove the launcher without a splash."""
    point = launcher_point_at_gaze(shell, panel_az, panel_el, yaw, pitch)
    if point is None or not launcher_contains_point(shell, *point):
        return False
    shell.launch_pose = (panel_az, panel_el)
    shell.pointer_motion(*point)
    shell.pointer_button(True)
    shell.pointer_button(False)
    if shell.active_app is None:
        return False
    hide_launcher(wm, shell, wid, "app-started")
    return True


class BTN2AppDrag:
    """Keep the BOSIO pointer pressed while BTN2 and the gaze are moving."""

    def __init__(self, wm):
        self.wm = wm
        self.held = False
        self.last_pose = None

    def press(self, yaw, pitch):
        if self.held:
            return
        self.wm.pointer_warp(yaw, pitch)
        self.wm.pointer_button(True)
        self.held = True
        self.last_pose = (yaw, pitch)

    def move(self, yaw, pitch):
        if self.held and (yaw, pitch) != self.last_pose:
            self.wm.pointer_warp(yaw, pitch)
            self.last_pose = (yaw, pitch)

    def release(self, yaw, pitch):
        if not self.held:
            return
        self.move(yaw, pitch)
        self.wm.pointer_button(False)
        self.held = False
        self.last_pose = None


def main():
    shell = BoayoLauncherShell(640, 360, "/home/xilinx/bosio_v2/boayo/apps.json")
    hide_panel_requested = [False]

    def request_panel_hide(_signal, _frame):
        hide_panel_requested[0] = True

    signal.signal(signal.SIGUSR1, request_panel_hide)
    with BosioWMClient("boayo-desktop") as wm:
        win = wm.create_window("BoAYO Launcher", azimuth=0, elevation=0,
                               width_deg=42, height_deg=30,
                               surface_width=640, surface_height=360, always_on_top=True)
        wid = win["window_id"]
        panel_az, panel_el = 0.0, 0.0
        last = 0.0
        last_surface_key = None
        panel_mapped = True
        app_drag = BTN2AppDrag(wm)
        last_left_press_serial = (wm.get_state().get("pointer") or {}).get("left_press_serial")
        last_mouse_left = False
        while True:
            now = time.monotonic()
            if hide_panel_requested[0]:
                hide_panel_requested[0] = False
                app_drag.release(panel_az, panel_el)
                hide_launcher(wm, shell, wid, "external-app")
                panel_mapped = False
            state = wm.get_state()
            pointer = state.get("pointer") or {}
            mouse_left = "left" in pointer.get("buttons", ())
            press_serial = pointer.get("left_press_serial")
            if press_serial is not None:
                if press_serial != last_left_press_serial and panel_mapped:
                    press = pointer.get("last_left_press") or {}
                    if not launcher_contains_gaze(shell, panel_az, panel_el,
                                                  press.get("azimuth", 0), press.get("elevation", 0)):
                        hide_launcher(wm, shell, wid, "outside-click")
                        panel_mapped = False
                last_left_press_serial = press_serial
            elif panel_mapped and mouse_left and not last_mouse_left:
                # Older BOSIO services expose only the current button state.
                if not launcher_contains_gaze(shell, panel_az, panel_el,
                                              pointer.get("azimuth", 0), pointer.get("elevation", 0)):
                    hide_launcher(wm, shell, wid, "outside-click")
                    panel_mapped = False
            last_mouse_left = mouse_left
            for event in wm.poll_events():
                if not panel_mapped or event.get("window_id") != wid:
                    continue
                if event.get("type") not in ("pointer_motion", "pointer_button"):
                    continue
                x = float(event["u"]) * shell.width
                y = float(event["v"]) * shell.height
                if (event["type"] == "pointer_button" and event.get("button") == "left" and
                        event.get("pressed") and not launcher_contains_point(shell, x, y)):
                    hide_launcher(wm, shell, wid, "outside-click")
                    panel_mapped = False
                    continue
                shell.pointer_motion(x, y)
                if event["type"] == "pointer_button" and event.get("button") == "left":
                    shell.launch_pose = (panel_az, panel_el)
                    shell.pointer_button(event["pressed"])
                    if shell.active_app is not None:
                        hide_launcher(wm, shell, wid, "app-started")
                        panel_mapped = False
                        print(f"BOAYO_APP_STARTED {shell.last_launch}", flush=True)
            out = state.get("output") or {}
            yaw = math.degrees(out.get("sensor_yaw_mrad", 0) / 1000.0)
            pitch = math.degrees(out.get("sensor_pitch_mrad", 0) / 1000.0)
            for event in wm.poll_button_events():
                if event["pressed"] and event["button"] in (0, 1):
                    # BTN0/BTN1 bring the single launcher panel to current gaze.
                    app_drag.release(yaw, pitch)
                    wm.configure_window(wid, azimuth=yaw, elevation=pitch, mapped=True)
                    wm.focus_window(wid, raise_window=True)
                    panel_mapped = True
                    panel_az, panel_el = yaw, pitch
                    shell.visible = True
                    shell.selected_app = None
                    shell.active_app = None
                    print(f"BOAYO_PANEL_FOCUS BTN{event['button']} az={yaw:.2f} el={pitch:.2f}", flush=True)
                elif event["button"] == 2:
                    if event["pressed"]:
                        if panel_mapped and not launcher_contains_gaze(shell, panel_az, panel_el, yaw, pitch):
                            hide_launcher(wm, shell, wid, "outside-click")
                            panel_mapped = False
                            app_drag.press(yaw, pitch)
                        elif panel_mapped:
                            if click_launcher_at_gaze(wm, shell, wid, panel_az, panel_el, yaw, pitch):
                                panel_mapped = False
                                print(f"BOAYO_APP_STARTED {shell.last_launch}", flush=True)
                        else:
                            app_drag.press(yaw, pitch)
                    else:
                        app_drag.release(yaw, pitch)
            app_drag.move(yaw, pitch)
            shell.tick(now - last); last = now
            surface_key = shell.render_key()
            if panel_mapped and surface_key != last_surface_key:
                wm.update_surface(wid, shell.render())
                last_surface_key = surface_key
            time.sleep(1.0 / 30.0)

if __name__ == "__main__":
    main()


