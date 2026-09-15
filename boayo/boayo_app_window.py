"""BoAYo application surface and its own caption, inside one BOSIO window.

BOSIO's surface protocol is RGB24, so the gap around the content and caption
uses the compositor background instead of pretending to provide alpha.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from boayo_ui import ACCENT, BLACK, INK, MUTED, PANEL, WHITE, BoayoSurface, point_in_polygon
except ImportError:
    from .boayo_ui import ACCENT, BLACK, INK, MUTED, PANEL, WHITE, BoayoSurface, point_in_polygon


@dataclass(frozen=True)
class AppRect:
    x: int
    y: int
    width: int
    height: int


class BoayoAppFrame:
    """Draw app content and a caption box that stays within the window width."""

    def __init__(self, width, height, title, accent=ACCENT):
        self.width, self.height = int(width), int(height)
        if self.width < 240 or self.height < 170:
            raise ValueError("BoAYo app surface is too small for its caption")
        self.title = str(title)
        self.accent = tuple(accent)
        self.surface = BoayoSurface(width, height)
        margin = max(12, round(self.width * .055))
        self.content = AppRect(margin, 12, self.width - margin * 2, self.height - 88)
        self.caption = AppRect(margin, self.height - 62, self.width - margin * 2, 48)

    def controls(self):
        box = self.caption
        left, right = box.x, box.x + box.width
        cy = box.y + box.height // 2
        return {
            "resize_left": np.asarray(((left + 12, cy + 12), (left + 12, cy - 12), (left + 36, cy + 12)), dtype=np.float32),
            "close": np.asarray(((left + 56, cy - 12), (left + 82, cy - 12), (left + 69, cy + 12)), dtype=np.float32),
            "move": np.asarray(((left + 103, cy - 11), (left + 147, cy - 11), (left + 155, cy + 11), (left + 95, cy + 11)), dtype=np.float32),
            "resize_right": np.asarray(((right - 36, cy + 12), (right - 12, cy - 12), (right - 12, cy + 12)), dtype=np.float32),
        }

    def hit_test(self, u, v):
        x, y = float(u) * self.width, float(v) * self.height
        for name, polygon in self.controls().items():
            if point_in_polygon(x, y, polygon):
                return name
        if self.content.x <= x < self.content.x + self.content.width and self.content.y <= y < self.content.y + self.content.height:
            return "content"
        return None

    def render(self, draw_content):
        canvas = self.surface
        canvas.clear(BLACK)
        c, box = self.content, self.caption
        canvas.rounded_rect(c.x + 2, c.y + 3, c.width, c.height, 14, (13, 16, 21))
        canvas.rounded_rect(c.x, c.y, c.width, c.height, 14, WHITE)
        draw_content(canvas, c)
        canvas.rounded_rect(box.x + 2, box.y + 2, box.width, box.height, 12, (13, 16, 21))
        canvas.rounded_rect(box.x, box.y, box.width, box.height, 12, PANEL)
        for name, polygon in self.controls().items():
            color = (216, 68, 55) if name == "close" else (92, 105, 122)
            canvas.rounded_polygon(polygon, 5, color)
        label_x = box.x + 170
        available = box.width - 230
        if available >= 70:
            scale = 2 if available >= 120 else 1
            chars = max(1, available // (7 * scale))
            canvas.text(self.title[:chars], label_x, box.y + 17, INK, scale=scale, bold=True)
        return canvas.image()


class BoayoApplicationWindow:
    """Register an app-owned BOSIO window and handle BoAYo caption actions."""

    def __init__(self, wm, title, azimuth, elevation, width_deg, height_deg,
                 width=400, height=300, accent=ACCENT):
        self.wm = wm
        self.frame = BoayoAppFrame(width, height, title, accent)
        info = wm.create_window(title, azimuth=azimuth, elevation=elevation,
                                width_deg=width_deg, height_deg=height_deg,
                                surface_width=width, surface_height=height,
                                decorated=False)
        self.window_id = info["window_id"] if isinstance(info, dict) else int(info)
        self.azimuth, self.elevation = float(azimuth), float(elevation)
        self.width_deg, self.height_deg = float(width_deg), float(height_deg)
        self.drag = None
        self.pressed_zone = None
        self.closed = False

    def present(self, draw_content):
        """Draw content with a BoayoSurface callback; SDK adds the caption."""
        self.wm.update_surface(self.window_id, self.frame.render(draw_content))

    def present_rgb(self, rgb, fit="contain"):
        """Put a rendered RGB image in the content area, then add the caption."""
        image = np.asarray(rgb, dtype=np.uint8)
        if image.ndim != 3 or image.shape[2] != 3 or not image.shape[0] or not image.shape[1]:
            raise ValueError("rgb must have shape (height,width,3)")
        if fit not in ("contain", "stretch"):
            raise ValueError("fit must be 'contain' or 'stretch'")

        def draw(canvas, rect):
            available_w, available_h = rect.width - 16, rect.height - 16
            if fit == "contain":
                scale = min(available_w / image.shape[1], available_h / image.shape[0])
                width = max(1, min(available_w, round(image.shape[1] * scale)))
                height = max(1, min(available_h, round(image.shape[0] * scale)))
            else:
                width, height = available_w, available_h
            xs = np.linspace(0, image.shape[1] - 1, width)
            ys = np.linspace(0, image.shape[0] - 1, height)
            x0, y0 = np.floor(xs).astype(np.int32), np.floor(ys).astype(np.int32)
            x1 = np.minimum(x0 + 1, image.shape[1] - 1)
            y1 = np.minimum(y0 + 1, image.shape[0] - 1)
            ax, ay = (xs - x0)[None, :, None], (ys - y0)[:, None, None]
            pixels = (image[y0[:, None], x0[None, :]] * (1 - ax) * (1 - ay) +
                      image[y0[:, None], x1[None, :]] * ax * (1 - ay) +
                      image[y1[:, None], x0[None, :]] * (1 - ax) * ay +
                      image[y1[:, None], x1[None, :]] * ax * ay)
            x = rect.x + (rect.width - width) // 2
            y = rect.y + (rect.height - height) // 2
            canvas.pixels[y:y + height, x:x + width] = np.rint(pixels).astype(np.uint8)

        self.present(draw)

    def handle_event(self, event):
        if event.get("window_id") != self.window_id or self.closed:
            return None
        kind = event.get("type")
        if kind == "pointer_button" and event.get("button") == "left":
            zone = self.frame.hit_test(event.get("u", -1), event.get("v", -1))
            if event.get("pressed"):
                self.pressed_zone = zone
                if zone in ("move", "resize_left", "resize_right"):
                    self.drag = (zone, float(event["u"]), float(event["v"]),
                                 self.azimuth, self.elevation, self.width_deg, self.height_deg)
                return zone
            if self.drag is not None:
                self.drag = None
            elif zone == "close" and self.pressed_zone == "close":
                self.wm.destroy_window(self.window_id)
                self.closed = True
            self.pressed_zone = None
            return zone
        if kind == "pointer_motion" and self.drag is not None:
            zone, u0, v0, az, el, wdeg, hdeg = self.drag
            du, dv = float(event["u"]) - u0, float(event["v"]) - v0
            if zone == "move":
                self.azimuth, self.elevation = az + du * wdeg, max(-89.5, min(89.5, el - dv * hdeg))
                self.wm.configure_window(self.window_id, azimuth=self.azimuth, elevation=self.elevation)
            else:
                factor = -1 if zone == "resize_left" else 1
                self.width_deg = max(10, min(100, wdeg + factor * du * wdeg))
                self.height_deg = max(8, min(80, hdeg + dv * hdeg))
                self.wm.configure_window(self.window_id, width_deg=self.width_deg, height_deg=self.height_deg)
            return zone
        return None

    def poll_events(self):
        for event in self.wm.poll_events():
            self.handle_event(event)
        return not self.closed
