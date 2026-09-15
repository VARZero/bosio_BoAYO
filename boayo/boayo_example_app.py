#!/usr/bin/env python3
"""BoAYO external-window example: registers a real IPC window and animates it."""
from __future__ import annotations
import os, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bosio_wm_client import BosioWMClient

def main():
    log_path = os.environ.get("BOAYO_EXAMPLE_LOG", "/tmp/boayo-example-app.log")
    with open(log_path, "a", encoding="utf-8") as stream:
        stream.write(f"dashboard started pid={os.getpid()}\n"); stream.flush()
    h, w = 240, 360
    with BosioWMClient("dashboard") as wm:
        window = wm.create_window("Dashboard", azimuth=float(os.environ.get("BOAYO_APP_AZIMUTH", 0)), elevation=float(os.environ.get("BOAYO_APP_ELEVATION", 0)),
                                  width_deg=38, height_deg=28,
                                  surface_width=w, surface_height=h)
        wid = window["window_id"] if isinstance(window, dict) else int(window)
        frame = np.full((h, w, 3), (248, 250, 253), dtype=np.uint8)
        frame[72:148, 90:166] = (52, 124, 255)
        frame[106:110, 188:300] = (52, 124, 255)
        wm.update_surface(wid, frame)
        while True:
            time.sleep(1.0)

if __name__ == "__main__":
    main()

