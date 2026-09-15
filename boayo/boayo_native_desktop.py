#!/usr/bin/env python3
"""BoAYO desktop backed entirely by BOSIO Window Manager windows."""
from __future__ import annotations
import math, signal, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bosio_wm_client import BosioWMClient
from boayo_shell import BoayoLauncherShell
from bosio_window_manager import _direction, _basis


def click_launcher_at_gaze(wm, shell, wid, panel_az, panel_el, yaw, pitch):
    """Run the pointed JSON app and remove the launcher without a splash."""
    shell.launch_pose = (panel_az, panel_el)
    direction = _direction(yaw, pitch)
    center, right, up = _basis(panel_az, panel_el)
    dot = float(direction @ center)
    if dot <= 0:
        return False
    x = float(direction @ right) / dot / math.tan(math.radians(21.0))
    y = float(direction @ up) / dot / math.tan(math.radians(15.0))
    if abs(x) > 1 or abs(y) > 1:
        return False
    shell.pointer_motion((x + 1) * .5 * shell.width, (1 - y) * .5 * shell.height)
    shell.pointer_button(True)
    shell.pointer_button(False)
    if shell.active_app is None:
        return False
    wm.configure_window(wid, mapped=False)
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
        while True:
            now = time.monotonic()
            if hide_panel_requested[0]:
                hide_panel_requested[0] = False
                app_drag.release(panel_az, panel_el)
                wm.configure_window(wid, mapped=False)
                panel_mapped = False
                shell.visible = False
                print("BOAYO_PANEL_HIDDEN external-app", flush=True)
            state = wm.get_state()
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
                    if panel_mapped and event["pressed"]:
                        if click_launcher_at_gaze(wm, shell, wid, panel_az, panel_el, yaw, pitch):
                            panel_mapped = False
                            print(f"BOAYO_APP_STARTED {shell.last_launch}", flush=True)
                    elif not panel_mapped:
                        if event["pressed"]:
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


