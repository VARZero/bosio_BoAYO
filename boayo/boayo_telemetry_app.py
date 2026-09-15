#!/usr/bin/env python3
"""BoAYO external telemetry demo window."""
from __future__ import annotations
import os, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bosio_wm_client import BosioWMClient

def main():
    h, w = 220, 360
    with BosioWMClient("telemetry") as wm:
        info = wm.create_window("Telemetry", azimuth=float(os.environ.get("BOAYO_APP_AZIMUTH", 20)), elevation=float(os.environ.get("BOAYO_APP_ELEVATION", 0)),
                                width_deg=36, height_deg=26,
                                surface_width=w, surface_height=h)
        wid = info["window_id"]
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (20, 28, 38)
        frame[18:66, 18:w-18] = (51, 181, 122)
        frame[88:94, 18:w-18] = (80, 100, 120)
        frame[150:156, 18:w-18] = (51, 181, 122)
        t = 0
        while True:
            pulse = int((np.sin(t * 0.12) + 1.0) * 0.5 * (w - 36))
            frame[88:94, 18:18 + pulse] = (51, 181, 122)
            frame[150:156, 18:18 + ((t * 7) % (w - 36))] = (52, 124, 255)
            wm.update_surface(wid, frame)
            t += 1
            time.sleep(1.0 / 12.0)

if __name__ == "__main__":
    main()

