"""Fixed-angular-size caption buttons, independent of the app's RGB surface."""
from __future__ import annotations

import math

try:
    from boayo_ui import BoayoSurface
    from boayo_theme import EDGE, FOCUS, TEXT, DANGER
    from boayo_surface_updates import SurfacePublisher
except ImportError:
    from .boayo_ui import BoayoSurface
    from .boayo_theme import EDGE, FOCUS, TEXT, DANGER
    from .boayo_surface_updates import SurfacePublisher


BUTTON_DEGREES = 4.0
BUTTON_PIXELS = 40


def button_image(name, selected=False):
    canvas = BoayoSurface(BUTTON_PIXELS, BUTTON_PIXELS)
    canvas.rounded_rect(0, 0, 40, 40, 8, FOCUS if selected else EDGE)
    fill = DANGER if name == "close" else ((96, 128, 160) if selected else (64, 64, 64))
    canvas.rounded_rect(1, 1, 38, 38, 7, fill)
    if name == "move":
        for x in (15, 24):
            for y in (11, 20, 29):
                canvas.circle(x, y, 2, TEXT)
    elif name == "close":
        for step in range(18):
            canvas.rect(10 + step, 10 + step, 3, 3, TEXT)
            canvas.rect(27 - step, 10 + step, 3, 3, TEXT)
    else:
        for step in range(18):
            canvas.rect(10 + step, 27 - step, 3, 3, TEXT)
        canvas.rect(19, 10, 11, 3, TEXT)
        canvas.rect(27, 10, 3, 11, TEXT)
        canvas.rect(10, 19, 3, 11, TEXT)
        canvas.rect(10, 27, 11, 3, TEXT)
    return canvas.image()


class CaptionControls:
    """Three small windows form one logical focus group with their owning app."""
    def __init__(self, app):
        self.app = app
        self.ids = {}
        self.publishers = {}
        self.geometry = {}
        self.appearance = {}

    def owns(self, wid):
        return wid in self.ids.values()

    def sync(self):
        app = self.app
        visible = app.focused and not app.closed and not app.minimized and not app._transition
        if not visible:
            for name, wid in self.ids.items():
                if self.geometry.get(name) is not None:
                    app.wm.configure_window(wid, mapped=False)
                    self.geometry[name] = None
            return
        # Anchor outside the shell. Offsets are measured in angle, so even a
        # very small app never has to surrender content pixels to its controls.
        frame = app.frame
        shell = frame.shell
        half_w = math.tan(math.radians(app.width_deg / 2))
        half_h = math.tan(math.radians(app.height_deg / 2))
        right = math.atan((2 * (shell.x + shell.width) / frame.width - 1) * half_w)
        left = math.atan((2 * shell.x / frame.width - 1) * half_w)
        gap = math.radians(BUTTON_DEGREES / 2 + .6)
        right_u = (math.tan(right + gap) / half_w + 1) / 2
        left_u = (math.tan(left - gap) / half_w + 1) / 2
        # Keep top and bottom button centers at least one button-height apart.
        top = max(math.radians(BUTTON_DEGREES / 2 + .3),
                  math.atan((1 - 2 * shell.y / frame.height) * half_h) - math.radians(BUTTON_DEGREES / 2))
        top_v = (1 - math.tan(top) / half_h) / 2
        anchors = {"move": (left_u, .5), "resize_right": (right_u, 1-top_v), "close": (right_u, top_v)}
        for name, (u, v) in anchors.items():
            az, el = app._gaze_at_surface(app.azimuth, app.elevation, app.width_deg, app.height_deg, u, v)
            pose = (az, el)
            if name not in self.ids:
                info = app.wm.create_window(
                    name + ": " + frame.title, azimuth=az, elevation=el,
                    width_deg=BUTTON_DEGREES, height_deg=BUTTON_DEGREES,
                    surface_width=40, surface_height=40, decorated=False,
                    always_on_top=True, focus_on_create=False,
                    workspace={"role": "caption", "parent": app.window_id, "control": name},
                    shape=[[0, 0, 40, 40, 8]])
                wid = info["window_id"] if isinstance(info, dict) else int(info)
                self.ids[name] = wid
                self.publishers[name] = SurfacePublisher(app.wm, wid)
                self.geometry[name] = pose
            elif self.geometry.get(name) != pose:
                app.wm.configure_window(self.ids[name], mapped=True, azimuth=az, elevation=el)
                self.geometry[name] = pose
            selected = name == frame.hovered or name == frame.dragging
            if self.appearance.get(name) != selected:
                self.publishers[name].publish(button_image(name, selected))
                self.appearance[name] = selected

    def route(self, event):
        name = next((name for name, wid in self.ids.items() if wid == event.get("window_id")), None)
        if name is None:
            return event
        inside = 0 <= event.get("u", -1) <= 1 and 0 <= event.get("v", -1) <= 1
        return dict(event, window_id=self.app.window_id, _caption_control=name if inside else None,
                    _caption_source=self.ids[name])

    def close(self):
        for wid in self.ids.values():
            self.app.wm.destroy_window(wid)
        self.ids.clear()
        self.publishers.clear()
