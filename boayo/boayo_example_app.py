#!/usr/bin/env python3
"""Live Dashboard for the spherical workspace, opened directly by BTN0."""
from __future__ import annotations
import math, os, time
from boayo_sdk import BoayoSDK
from boayo_theme import CHROME, RAISED, FOCUS, TEXT, SUBTLE, orbit_mark


def main():
    with BoayoSDK("dashboard") as sdk:
        app = sdk.create_window("Dashboard", width_deg=38, height_deg=28,
                                width=640, height=440, accent=FOCUS)
        next_refresh = 0
        last_content_key = None
        while not app.closed:
            sdk.poll_events()
            now = time.monotonic()
            if now >= next_refresh:
                state = sdk.wm.get_state()
                output = state.get("output") or {}
                apps = [w for w in state.get("windows", ()) if w.get("workspace", {}).get("role") == "app"]
                stored = sum(w["workspace"].get("state") == "minimized" for w in apps)
                yaw = round(math.degrees(output.get("sensor_yaw_mrad", 0) / 1000))
                pitch = round(math.degrees(output.get("sensor_pitch_mrad", 0) / 1000))
                content_key = (len(apps), stored, yaw, pitch)
                if content_key == last_content_key or app.minimized:
                    next_refresh = now + .5
                    time.sleep(.03)
                    continue
                def draw(canvas, rect):
                    x, y, w, h = rect.x, rect.y, rect.width, rect.height
                    canvas.rect(x, y, w, h, CHROME)
                    canvas.text("YOUR WORKSPACE", x + 22, y + 25, TEXT, scale=3, bold=True)
                    for col, (title, value) in enumerate((("OPEN", len(apps) - stored), ("STORED", stored))):
                        tx = x + 22 + col * (w // 2)
                        canvas.rounded_rect(tx, y + 80, w // 2 - 36, 98, 12, RAISED)
                        canvas.text(title, tx + 16, y + 92, SUBTLE, scale=2)
                        canvas.text(str(value), tx + 16, y + 123, FOCUS, scale=4, bold=True)
                    yaw = math.degrees(output.get("sensor_yaw_mrad", 0) / 1000)
                    pitch = math.degrees(output.get("sensor_pitch_mrad", 0) / 1000)
                    canvas.text(f"YAW {yaw:+.0f}  PITCH {pitch:+.0f}", x + 22, y + 210, TEXT, scale=2)
                    canvas.text("BTN1 APPS / BTN2 HOLD TO MOVE", x + 22, y + 251, SUBTLE, scale=2)
                    canvas.text("LOOK DOWN TO FIND STORED WINDOWS", x + 22, y + 291, SUBTLE, scale=1)
                app.present(draw)
                last_content_key = content_key
                next_refresh = now + .5
            time.sleep(.03)


if __name__ == "__main__":
    main()
