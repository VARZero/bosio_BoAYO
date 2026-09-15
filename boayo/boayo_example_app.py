#!/usr/bin/env python3
"""BoAYO external-window example: registers a real IPC window and animates it."""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bosio_wm_client import BosioWMClient
from boayo_app_window import BoayoApplicationWindow

def main():
    log_path = os.environ.get("BOAYO_EXAMPLE_LOG", "/tmp/boayo-example-app.log")
    with open(log_path, "a", encoding="utf-8") as stream:
        stream.write(f"dashboard started pid={os.getpid()}\n"); stream.flush()
    with BosioWMClient("dashboard") as wm:
        app = BoayoApplicationWindow(wm, "Dashboard",
                                     float(os.environ.get("BOAYO_APP_AZIMUTH", 0)),
                                     float(os.environ.get("BOAYO_APP_ELEVATION", 0)),
                                     width_deg=38, height_deg=28, accent=(52, 124, 255))
        def draw(canvas, rect):
            canvas.text("DASHBOARD", rect.x + 22, rect.y + 18, (22, 29, 40), scale=3, bold=True)
            canvas.rounded_rect(rect.x + 22, rect.y + 60, 82, 78, 14, (52, 124, 255))
            canvas.rounded_rect(rect.x + 122, rect.y + 96, rect.width - 152, 8, 4, (52, 124, 255))
            canvas.text("LIVE WINDOW", rect.x + 22, rect.y + 156, (105, 116, 132), scale=2)
        app.present(draw)
        while app.poll_events():
            time.sleep(.05)

if __name__ == "__main__":
    main()

