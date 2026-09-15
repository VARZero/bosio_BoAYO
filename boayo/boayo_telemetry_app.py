#!/usr/bin/env python3
"""BoAYO external telemetry demo window."""
from __future__ import annotations
import os, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bosio_wm_client import BosioWMClient
from boayo_app_window import BoayoApplicationWindow

def main():
    with BosioWMClient("telemetry") as wm:
        app = BoayoApplicationWindow(wm, "Telemetry",
                                     float(os.environ.get("BOAYO_APP_AZIMUTH", 20)),
                                     float(os.environ.get("BOAYO_APP_ELEVATION", 0)),
                                     width_deg=36, height_deg=26, accent=(51, 181, 122))
        t = 0
        while app.poll_events():
            def draw(canvas, rect):
                canvas.text("TELEMETRY", rect.x + 22, rect.y + 18, (22, 29, 40), scale=3, bold=True)
                pulse = int((np.sin(t * .12) + 1) * .5 * (rect.width - 48))
                canvas.rounded_rect(rect.x + 22, rect.y + 76, rect.width - 44, 14, 7, (211, 220, 230))
                if pulse > 10:
                    canvas.rounded_rect(rect.x + 22, rect.y + 76, pulse, 14, 7, (51, 181, 122))
                canvas.rounded_rect(rect.x + 22, rect.y + 120, rect.width - 44, 10, 5, (211, 220, 230))
                canvas.rounded_rect(rect.x + 22, rect.y + 120, 14 + (t * 7) % (rect.width - 58), 10, 5, (52, 124, 255))
            app.present(draw)
            t += 1
            time.sleep(1.0 / 12.0)

if __name__ == "__main__":
    main()

