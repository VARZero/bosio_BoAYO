#!/usr/bin/env python3
"""Run BoAYo as the owner of a complete BOSIO output scene on PYNQ-Z2."""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

try:
    from boayo_shell import BoayoLauncherShell, BoayoScene, BoayoShell, BoayoWorkspace
except ImportError:
    from .boayo_shell import BoayoLauncherShell, BoayoScene, BoayoShell, BoayoWorkspace


def save_preview(path, image):
    path = Path(path)
    try:
        from PIL import Image
        Image.fromarray(image).save(path)
    except ImportError:
        path = path.with_suffix(".ppm")
        with path.open("wb") as stream:
            stream.write(f"P6\n{image.shape[1]} {image.shape[0]}\n255\n".encode("ascii"))
            stream.write(image.tobytes())
    return path


def preview(args):
    try:
        from bosio_view_simulator import render_bosio_view
    except ImportError:
        from .bosio_view_simulator import render_bosio_view
    shell = (BoayoLauncherShell(args.surface_width, args.surface_height, args.apps)
             if args.launcher else BoayoShell(args.surface_width, args.surface_height))
    if args.preview_focus:
        points = shell.caption_polygons()[args.preview_focus]
        shell.pointer_motion(*points.mean(axis=0))
        shell.tick(1.0)
    if args.preview_source:
        image = shell.render()
    else:
        scene = BoayoScene(shell, args.m, args.azimuth, args.elevation, args.width_deg, args.height_deg)
        image = render_bosio_view(scene.render(), args.m, fov_h=args.view_fov_h,
                                  fov_v=args.view_fov_v,
                                  width=args.preview_width, height=args.preview_height)
    output = save_preview(args.preview, image)
    print(f"BOAYO_PREVIEW {output}", flush=True)


def run_pynq(args):
    from bosio_buttons import ButtonDebouncer
    from bosio_driver_v2 import BosioV2

    shell = BoayoShell(args.surface_width, args.surface_height)
    scene = BoayoScene(shell, args.m, args.azimuth, args.elevation, args.width_deg, args.height_deg)
    driver = BosioV2(args.bitstream, args.m, download=args.program_bitstream)
    debouncer = ButtonDebouncer(driver.buttons.read_state(), 0.03)
    pressed = False
    last = time.monotonic()

    try:
        driver.upload(scene.render())
        driver.set_pose(0, 0, 0)
        driver.start()
        driver.use_sensor(True)
        print("BOAYO_READY BTN0=select/drag BTN1=reopen", flush=True)
        while True:
            now = time.monotonic()
            status = driver.status()
            yaw = math.degrees(status["sensor_yaw_mrad"] / 1000.0) * args.gaze_yaw_sign
            pitch = math.degrees(status["sensor_pitch_mrad"] / 1000.0) * args.gaze_pitch_sign
            before = (shell.hovered, tuple(vars(shell.window).values()), shell.visible)
            scene.gaze(yaw, pitch)
            for event in debouncer.update(driver.buttons.read_state(), now):
                if event["button"] == 0:
                    pressed = event["pressed"]
                    shell.pointer_button(pressed)
                elif event["button"] == 1 and event["pressed"]:
                    shell.visible = True
            animated = shell.tick(now - last)
            after = (shell.hovered, tuple(vars(shell.window).values()), shell.visible)
            if animated or before != after or pressed:
                driver.upload(scene.render())
            last = now
            time.sleep(max(0.001, 1.0 / args.fps))
    except KeyboardInterrupt:
        pass
    finally:
        driver.close()


def run_daemon(args):
    try:
        from bosio_native_compositor import pack_scene
    except (ImportError, OSError):
        try:
            from bosio_geometry_v2 import pack_scene
        except ImportError:
            from .bosio_geometry_v2 import pack_scene
    try:
        from bosio_wm_client import BosioWMClient
    except ImportError:
        from .bosio_wm_client import BosioWMClient

    pressed = False
    last = time.monotonic()

    def make_ui(azimuth, elevation):
        if args.launcher or args.windows > 1:
            return BoayoWorkspace(args.m, azimuth, elevation, max(1, args.windows),
                                  launcher=args.launcher, apps_path=args.apps)
        return BoayoScene(BoayoShell(args.surface_width, args.surface_height), args.m,
                          azimuth, elevation, args.width_deg, args.height_deg)

    with BosioWMClient("boayo-desktop", args.socket) as bosio:
        capabilities = bosio.ping().get("features", [])
        if "scene-stream" not in capabilities:
            raise RuntimeError("running BOSIO daemon does not support scene-stream")
        bosio.claim_scene()
        try:
            state = bosio.get_state()
            status = state.get("output") or {}
            current_yaw = math.degrees(status.get("sensor_yaw_mrad", 0) / 1000.0) * args.gaze_yaw_sign
            current_pitch = math.degrees(status.get("sensor_pitch_mrad", 0) / 1000.0) * args.gaze_pitch_sign
            scene_azimuth = args.azimuth if args.fixed_origin else current_yaw
            scene_elevation = args.elevation if args.fixed_origin else current_pitch
            ui = make_ui(scene_azimuth, scene_elevation)
            words, _ = pack_scene(ui.render(), args.m)
            bosio.upload_scene_words(words)
            print("BOAYO_READY via BOSIO daemon; BTN0=select/open BTN1=relocate launcher", flush=True)
            while True:
                now = time.monotonic()
                state = bosio.get_state()
                status = state.get("output") or {}
                yaw = math.degrees(status.get("sensor_yaw_mrad", 0) / 1000.0) * args.gaze_yaw_sign
                pitch = math.degrees(status.get("sensor_pitch_mrad", 0) / 1000.0) * args.gaze_pitch_sign
                before = repr(ui)
                ui.gaze(yaw, pitch)
                pointer = state.get("pointer") or {}
                pointer_pose = (float(pointer.get("azimuth", 0.0)), float(pointer.get("elevation", 0.0)))
                if getattr(run_daemon, "last_pointer", None) != pointer_pose:
                    run_daemon.last_pointer = pointer_pose
                    run_daemon.mouse_deadline = now + 1.5
                if getattr(run_daemon, "mouse_deadline", 0.0) > now:
                    ui.mouse_gaze(*pointer_pose)
                scroll_serial = int(pointer.get("scroll_serial", 0))
                if scroll_serial != getattr(run_daemon, "scroll_serial", scroll_serial):
                    ui.scroll(float(pointer.get("scroll_delta", 0.0)))
                    run_daemon.scroll_serial = scroll_serial
                buttons = set(pointer.get("buttons", ()))
                previous_buttons = getattr(run_daemon, "pointer_buttons", set())
                for button in sorted(buttons - previous_buttons):
                    if button == "left":
                        ui.mouse_gaze(*pointer_pose)
                        ui.pointer_button(True)
                for button in sorted(previous_buttons - buttons):
                    if button == "left":
                        ui.mouse_gaze(*pointer_pose)
                        ui.pointer_button(False)
                run_daemon.pointer_buttons = buttons
                relocated = False
                for event in bosio.poll_button_events():
                    if event["button"] == 0:
                        pressed = event["pressed"]
                        if pressed and isinstance(ui, BoayoWorkspace):
                            ui.add_panel(yaw, pitch)
                        elif not isinstance(ui, BoayoWorkspace):
                            ui.pointer_button(pressed)
                    elif event["button"] == 1 and event["pressed"]:
                        # BTN1 recenters the launcher while preserving running panels.
                        scene_azimuth, scene_elevation = yaw, pitch
                        if isinstance(ui, BoayoWorkspace):
                            ui.recenter_launcher(scene_azimuth, scene_elevation)
                        else:
                            ui = make_ui(scene_azimuth, scene_elevation)
                        relocated = True
                animated = ui.tick(now - last)
                after = repr(ui)
                if animated or before != after or pressed or relocated:
                    words, _ = pack_scene(ui.render(), args.m)
                    bosio.upload_scene_words(words)
                last = now
                time.sleep(max(0.001, 1.0 / args.fps))
        finally:
            bosio.release_scene()


def main():
    parser = argparse.ArgumentParser(description="BoAYo gaze-first desktop for BOSIO/PYNQ-Z2")
    parser.add_argument("--bitstream", default=str(Path(__file__).with_name("bosio_v2.bit")))
    parser.add_argument("--program-bitstream", action="store_true", help="program PL instead of attaching to an already running BOSIO core")
    parser.add_argument("--m", type=int, choices=(8, 16, 32), default=16)
    parser.add_argument("--surface-width", type=int, default=640)
    parser.add_argument("--surface-height", type=int, default=360)
    parser.add_argument("--azimuth", type=float, default=0.0)
    parser.add_argument("--elevation", type=float, default=0.0)
    parser.add_argument("--width-deg", type=float, default=48.0)
    parser.add_argument("--height-deg", type=float, default=27.0)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--windows", type=int, default=1, help="number of spatial BoAYo windows")
    parser.add_argument("--launcher", action="store_true", help="run the gaze-first launcher surface")
    parser.add_argument("--apps", default=str(Path(__file__).with_name("apps.json")), help="launcher app configuration")
    parser.add_argument("--socket", default="/tmp/bosio-wm.sock")
    parser.add_argument("--direct-hardware", action="store_true", help="bypass the BOSIO daemon (development only)")
    parser.add_argument("--fixed-origin", action="store_true", help="place the shell at --azimuth/--elevation instead of the initial gaze")
    parser.add_argument("--gaze-yaw-sign", type=float, choices=(-1.0, 1.0), default=1.0)
    parser.add_argument("--gaze-pitch-sign", type=float, choices=(-1.0, 1.0), default=1.0)
    parser.add_argument("--preview", help="render the BoAYo canvas locally instead of using PYNQ")
    parser.add_argument("--preview-focus", choices=("resize_left", "close", "move", "resize_right"))
    parser.add_argument("--preview-source", action="store_true", help="show the source canvas before BOSIO sampling")
    parser.add_argument("--preview-width", type=int, default=1280)
    parser.add_argument("--preview-height", type=int, default=720)
    parser.add_argument("--view-fov-h", type=float, default=60.0)
    parser.add_argument("--view-fov-v", type=float, default=45.0)
    args = parser.parse_args()
    if args.preview:
        preview(args)
    elif args.direct_hardware:
        run_pynq(args)
    else:
        run_daemon(args)


if __name__ == "__main__":
    main()
