"""Render the actual spherical compositor at three spatial-workspace stages."""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "boayo"), str(ROOT / "vendor" / "bosio_SphericalWM" / "sw")]

from PIL import Image, ImageDraw
from bosio_window_manager import SphericalWindowManager
from boayo_sdk import BoayoSDK
from boayo_spatial_workspace import SpatialWorkspace
from bosio_view_simulator import render_bosio_view


class LocalClient:
    def __init__(self, manager, owner):
        self.manager, self.owner = manager, owner
    def __getattr__(self, name):
        return lambda *args, **kwargs: getattr(self.manager, name)(self.owner, *args, **kwargs)
    def get_state(self):
        return self.manager.state()
    def focus_window(self, *args, **kwargs):
        return self.manager.focus_window(*args, **kwargs)
    def update_surface(self, wid, rgb):
        height, width = rgb.shape[:2]
        self.manager.update_surface(self.owner, wid, 0, 0, width, height,
                                    base64.b64encode(rgb.tobytes()).decode("ascii"))


def render_preview(destination, m=16):
    manager = SphericalWindowManager(m=m)
    sdk = BoayoSDK("preview-app", wm=LocalClient(manager, "app"))
    workspace = SpatialWorkspace(LocalClient(manager, "desktop"))
    studio = sdk.create_window("STUDIO", azimuth=0, elevation=5, width_deg=38, height_deg=28, width=640, height=440)
    terminal = sdk.create_window("TERMINAL", azimuth=-29, elevation=2, width_deg=22, height_deg=18)
    notes = sdk.create_window("NOTES", azimuth=28, elevation=6, width_deg=20, height_deg=24)

    def editor(canvas, rect):
        canvas.rect(rect.x, rect.y, rect.width, rect.height, (32, 32, 64))
        canvas.text("SPHERICAL WORKSPACE", rect.x + 18, rect.y + 20, (160, 192, 192), scale=3, bold=True)
        for row, text in enumerate(("WINDOWS LIVE AROUND YOU", "YAW   :  0 DEG", "PITCH :  5 DEG", "GRAB EDGE TO MOVE", "LOWER WINDOW TO STORE")):
            canvas.text(text, rect.x + 18, rect.y + 85 + row * 37, (192, 192, 224), scale=2)
    studio.present(editor)
    terminal.present(lambda canvas, rect: canvas.card(rect.x + 8, rect.y + 12, rect.width - 16, rect.height - 24, "TERMINAL", "READY"))
    notes.present(lambda canvas, rect: canvas.card(rect.x + 8, rect.y + 12, rect.width - 16, rect.height - 24, "NOTES", "TODAY"))
    manager.focus_window(studio.window_id)
    sdk.poll_events()
    frames = []
    def capture(label, yaw=0, pitch=0):
        view = render_bosio_view(manager.render(), m=m, yaw=yaw, pitch=pitch,
                                  fov_h=90, fov_v=56, width=960, height=540)
        panel = Image.new("RGB", (960, 578), (8, 16, 24))
        panel.paste(Image.fromarray(view), (0, 38))
        ImageDraw.Draw(panel).text((16, 12), label, fill=(224, 240, 240))
        frames.append(panel)
    capture("1  WORK AREA / world-anchored application windows")
    for window in (terminal, notes):
        window.minimize()
        window.tick(window._transition[0] + .3)
    workspace.sync(manager.state())
    capture("2  LOOK DOWN / position-based storage cards", pitch=-35)
    target = notes.window_id
    card = manager.windows[workspace.cards[target]]
    manager.pointer_warp(card.azimuth, card.elevation)
    manager.pointer_button("left", True)
    for event in workspace.wm.poll_events():
        workspace.handle_event(event)
    manager.pointer_warp(28, -8)
    for event in workspace.wm.poll_events():
        workspace.handle_event(event)
    capture("3  LIFT CARD / release to place at preview", yaw=20, pitch=-12)
    output = Image.new("RGB", (960, 578 * len(frames)), (8, 16, 24))
    for i, frame in enumerate(frames):
        output.paste(frame, (0, i * 578))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        frame.save(destination.with_name(destination.stem + f"-{i + 1}.png"))
    output.save(destination)
    print(destination.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/spatial-workspace.png")
    parser.add_argument("--m", type=int, choices=(8, 16, 32), default=16)
    arguments = parser.parse_args()
    render_preview(arguments.output, arguments.m)
