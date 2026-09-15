#!/usr/bin/env python3
"""BoAYO external telemetry demo window."""
from __future__ import annotations
import time
import numpy as np
from boayo_sdk import BoayoSDK

def main():
    with BoayoSDK("telemetry") as sdk:
        app = sdk.create_window("Telemetry", width_deg=36, height_deg=26,
                                accent=(51, 181, 122))
        t = 0
        while not app.closed:
            sdk.poll_events()
            def draw(canvas, rect):
                canvas.text("TELEMETRY", rect.x + 22, rect.y + 18, (22, 29, 40), scale=3, bold=True)
                pulse = int((np.sin(t * .12) + 1) * .5 * (rect.width - 48))
                canvas.rounded_rect(rect.x + 22, rect.y + 76, rect.width - 44, 14, 7, (211, 220, 230))
                if pulse > 10:
                    canvas.rounded_rect(rect.x + 22, rect.y + 76, pulse, 14, 7, (51, 181, 122))
                canvas.rounded_rect(rect.x + 22, rect.y + 120, rect.width - 44, 10, 5, (211, 220, 230))
                canvas.rounded_rect(rect.x + 22, rect.y + 120, 14 + (t * 7) % (rect.width - 58), 10, 5, (52, 124, 255))
            if app.closed:
                break
            app.present(draw)
            t += 1
            time.sleep(1.0 / 12.0)

if __name__ == "__main__":
    main()

