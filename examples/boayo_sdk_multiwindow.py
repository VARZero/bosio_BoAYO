#!/usr/bin/env python3
"""Standalone BoAYo SDK demo: two app-owned windows over the BOSIO stack."""

import argparse
import time

import numpy as np

from boayo_sdk import BoayoSDK, INK


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=20.0)
    args = parser.parse_args()
    with BoayoSDK("sdk-multiwindow-demo") as sdk:
        first = sdk.create_window("SDK Demo A", azimuth=30, elevation=-59,
                                  width_deg=32, height_deg=24, accent=(52, 124, 255))
        second = sdk.create_window("SDK Demo B", azimuth=70, elevation=-59,
                                   width_deg=32, height_deg=24, accent=(51, 181, 122))

        def draw(canvas, content):
            canvas.text("APP A", content.x + 20, content.y + 20, INK, scale=3, bold=True)
            canvas.rounded_rect(content.x + 24, content.y + 72, 120, 64, 14, (52, 124, 255))

        first.present(draw)
        second.present_rgb(np.full((100, 160, 3), (51, 181, 122), dtype=np.uint8))
        print("SDK_WINDOWS", sorted(sdk.windows), flush=True)
        until = time.monotonic() + args.seconds
        while sdk.windows and time.monotonic() < until:
            for event in sdk.poll_events():
                if event.type == "pointer_button" and event.pressed:
                    print(f"SDK_CLICK {event.window_id} {event.x:.1f} {event.y:.1f}", flush=True)
            time.sleep(.05)


if __name__ == "__main__":
    main()
