#!/usr/bin/env python3
"""BoAYO desktop backed entirely by BOSIO Window Manager windows."""
from __future__ import annotations
import math, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bosio_wm_client import BosioWMClient
from boayo_shell import BoayoLauncherShell
from bosio_window_manager import _direction, _basis

def main():
    shell = BoayoLauncherShell(640, 360, "/home/xilinx/bosio_v2/boayo/apps.json")
    with BosioWMClient("boayo-desktop") as wm:
        win = wm.create_window("BoAYO Launcher", azimuth=0, elevation=0,
                               width_deg=42, height_deg=30,
                               surface_width=640, surface_height=360, always_on_top=True)
        wid = win["window_id"]
        panel_az, panel_el = 0.0, 0.0
        last = 0.0
        while True:
            now = time.monotonic()
            state = wm.get_state()
            out = state.get("output") or {}
            yaw = math.degrees(out.get("sensor_yaw_mrad", 0) / 1000.0)
            pitch = math.degrees(out.get("sensor_pitch_mrad", 0) / 1000.0)
            for event in wm.poll_button_events():
                if event["pressed"] and event["button"] in (0, 1):
                    # BTN0/BTN1 bring the single launcher panel to current gaze.
                    wm.configure_window(wid, azimuth=yaw, elevation=pitch, mapped=True)
                    wm.focus_window(wid, raise_window=True)
                    panel_az, panel_el = yaw, pitch
                    shell.selected_app = None
                    shell.active_app = None
                    print(f"BOAYO_PANEL_FOCUS BTN{event['button']} az={yaw:.2f} el={pitch:.2f}", flush=True)
                elif event["button"] == 2 and event["pressed"]:
                    # Pass the launch gaze to the selected external app.
                    shell.launch_pose = (yaw, pitch)
                    # Project current gaze onto the launcher surface and click.
                    direction = _direction(yaw, pitch)
                    center, right, up = _basis(panel_az, panel_el)
                    dot = float(direction @ center)
                    if dot > 0:
                        x = float(direction @ right) / dot / math.tan(math.radians(21.0))
                        y = float(direction @ up) / dot / math.tan(math.radians(15.0))
                        if abs(x) <= 1 and abs(y) <= 1:
                            shell.pointer_motion((x + 1) * .5 * shell.width, (1 - y) * .5 * shell.height)
                            shell.pointer_button(True); shell.pointer_button(False)
                    print("BOAYO_BTN2_CLICK", flush=True)
            shell.tick(now - last); last = now
            wm.update_surface(wid, shell.render())
            time.sleep(1.0 / 30.0)

if __name__ == "__main__":
    main()


