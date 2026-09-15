#!/usr/bin/env python3
"""BoAYO desktop backed entirely by BOSIO Window Manager windows."""
from __future__ import annotations
import math, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bosio_wm_client import BosioWMClient
from boayo_shell import BoayoLauncherShell

def main():
    shell = BoayoLauncherShell(640, 360, "/home/xilinx/bosio_v2/boayo/apps.json")
    with BosioWMClient("boayo-desktop") as wm:
        win = wm.create_window("BoAYO Launcher", azimuth=0, elevation=0,
                               width_deg=42, height_deg=30,
                               surface_width=640, surface_height=360, always_on_top=True)
        wid = win["window_id"]
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
                    shell.selected_app = None
                    shell.active_app = None
                    print(f"BOAYO_PANEL_FOCUS BTN{event['button']} az={yaw:.2f} el={pitch:.2f}", flush=True)
                elif event["button"] == 2 and event["pressed"]:
                    # BTN2 is a click at gaze center. The launcher list starts
                    # near the upper middle of its surface, so map the center
                    # action to the first visible app row when no hit exists.
                    shell.pointer_motion(shell.width * .5, shell.window.y + 49)
                    shell.pointer_button(True); shell.pointer_button(False)
                    if shell.selected_app:
                        shell.launch_app(shell.selected_app)
                    print("BOAYO_BTN2_CLICK", flush=True)
            shell.tick(now - last); last = now
            wm.update_surface(wid, shell.render())
            time.sleep(1.0 / 30.0)

if __name__ == "__main__":
    main()


