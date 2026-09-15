#!/usr/bin/env python3
"""Live BoAYo SDK example with a changing bar and content click counter."""
from __future__ import annotations

import os
import time

from boayo_sdk import BoayoSDK


def main():
    clicks = 0
    step = 0
    with BoayoSDK("sdk-pulse") as sdk:
        window = sdk.create_window("SDK Pulse", width_deg=38, height_deg=28,
                                   accent=(52, 124, 255))
        print(f"SDK_PULSE_STARTED pid={os.getpid()} window_id={window.window_id}", flush=True)

        def draw(canvas, area):
            x = area.x + 24
            width = area.width - 48
            canvas.text("SDK PULSE", x, area.y + 22, (22, 29, 40), scale=3, bold=True)
            canvas.text("LIVE APP", x, area.y + 68, (64, 64, 64), scale=2)
            canvas.rounded_rect(x, area.y + 103, width, 24, 10, (224, 232, 240))
            fill = max(12, int(width * (step + 1) / 10))
            canvas.rounded_rect(x, area.y + 103, fill, 24, 10, (52, 124, 255))
            canvas.text(f"CLICKS {clicks:02d}", x, area.y + 151,
                        (22, 29, 40), scale=3, bold=True)

        window.present(draw)
        last_update = time.monotonic()
        while not window.closed:
            changed = False
            for event in sdk.poll_events():
                if (event.window_id == window.window_id and
                        event.type == "pointer_button" and event.pressed and
                        event.button == "left"):
                    clicks += 1
                    changed = True
                    print(f"SDK_PULSE_CLICK count={clicks} x={event.x:.1f} y={event.y:.1f}",
                          flush=True)
            now = time.monotonic()
            if now - last_update >= 1.0:
                step = (step + 1) % 10
                last_update = now
                changed = True
            if changed and not window.closed:
                window.present(draw)
            time.sleep(.05)
        print("SDK_PULSE_CLOSED", flush=True)


if __name__ == "__main__":
    main()
