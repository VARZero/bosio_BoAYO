"""BoAYo application surface and its own caption, inside one BOSIO window.

BOSIO's surface protocol is RGB24, so the gap around the content and caption
uses the compositor background instead of pretending to provide alpha.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

try:
    from boayo_surface_updates import SurfacePublisher
    from boayo_caption import CaptionControls, button_image
except ImportError:
    from .boayo_surface_updates import SurfacePublisher
    from .boayo_caption import CaptionControls, button_image

try:
    from boayo_theme import CHROME, EDGE, FOCUS, TEXT, SUBTLE, DANGER
except ImportError:
    from .boayo_theme import CHROME, EDGE, FOCUS, TEXT, SUBTLE, DANGER

try:
    from boayo_ui import ACCENT, BLACK, INK, MUTED, PANEL, WHITE, BoayoSurface, point_in_polygon, scaled_polygon
except ImportError:
    from .boayo_ui import ACCENT, BLACK, INK, MUTED, PANEL, WHITE, BoayoSurface, point_in_polygon, scaled_polygon


@dataclass(frozen=True)
class AppRect:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class BoayoWindowState:
    """One app window's angular extent, fixed RGB surface and focus."""

    window_id: int
    azimuth: float
    elevation: float
    width_deg: float
    height_deg: float
    surface_width: int
    surface_height: int
    content_width: int
    content_height: int
    focused: bool
    closed: bool
    minimized: bool = False
    interaction: str = "idle"


class BoayoAppFrame:
    """Draw a continuous RGB frame with title and edge-mounted controls."""

    def __init__(self, width, height, title, accent=ACCENT):
        self.width, self.height = int(width), int(height)
        if self.width < 240 or self.height < 170:
            raise ValueError("BoAYo app surface is too small for its caption")
        self.title = str(title)
        self.accent = tuple(accent)
        self.surface = BoayoSurface(width, height)
        margin = 50
        self.content = AppRect(margin, 48, self.width - margin * 2, self.height - 82)
        self.shell = AppRect(48, 4, self.width - 96, self.height - 12)
        self.caption = AppRect(0, 0, self.width, self.height)
        self.focused = False
        self.external_controls = False
        self.hovered = None
        self.dragging = None
        self.compact = False
        mask = BoayoSurface(self.width, self.height, (0, 0, 0))
        shell = self.shell
        mask.rounded_rect(shell.x, shell.y, shell.width, shell.height, 14, (255,255,255))
        coverage = mask.pixels[:,:,0]
        self._clip_outside = coverage == 0
        self._clip_edges = (coverage > 0) & (coverage < 255)
        self._edge_alpha = coverage[self._clip_edges,None].astype(np.float32) / 255
        self._chrome_key = None
        self._chrome_pixels = None

    def controls(self):
        cy = self.height // 2
        x, y = self.width - 44, self.height - 46
        return {
            "move": np.asarray(((4, cy - 20), (44, cy - 20), (44, cy + 20), (4, cy + 20)), dtype=np.float32),
            "resize_right": np.asarray(((x, y), (x + 40, y), (x + 40, y + 40), (x, y + 40)), dtype=np.float32),
            "close": np.asarray(((self.width - 44, 6), (self.width - 4, 6),
                                 (self.width - 4, 46), (self.width - 44, 46)), dtype=np.float32),
        }

    def shape_rects(self):
        s = self.shell
        rects = [[s.x, s.y, s.width, s.height, 14]]
        for polygon in (self.controls().values() if self.focused and not self.external_controls else ()):
            x,y = polygon.min(axis=0)
            w,h = polygon.max(axis=0) - polygon.min(axis=0)
            rects.append([float(x), float(y), float(w), float(h), 8])
        return rects

    def hit_test(self, u, v):
        x, y = float(u) * self.width, float(v) * self.height
        for name, polygon in (self.controls().items() if self.focused else ()):
            if point_in_polygon(x, y, scaled_polygon(polygon, 1.25)):
                return name
        if self.content.x <= x < self.content.x + self.content.width and self.content.y <= y < self.content.y + self.content.height:
            return "content"
        return None

    def render(self, draw_content):
        key = (self.title, self.accent, self.focused, self.hovered, self.dragging, self.external_controls)
        if key != self._chrome_key:
            self._chrome_pixels = self._render_uncached(lambda canvas, rect: None).copy()
            self._chrome_key = key
        canvas = self.surface
        canvas.pixels[:] = self._chrome_pixels
        c = self.content
        draw_content(canvas,c)
        # App callbacks own the content rectangle; keep cached chrome intact.
        canvas.pixels[:c.y] = self._chrome_pixels[:c.y]
        canvas.pixels[c.y+c.height:] = self._chrome_pixels[c.y+c.height:]
        canvas.pixels[c.y:c.y+c.height,:c.x] = self._chrome_pixels[c.y:c.y+c.height,:c.x]
        canvas.pixels[c.y:c.y+c.height,c.x+c.width:] = self._chrome_pixels[c.y:c.y+c.height,c.x+c.width:]
        return canvas.image()

    def _render_uncached(self, draw_content):
        canvas = self.surface
        canvas.clear(BLACK)
        c, shell = self.content, self.shell
        # The shell is separate from the floating controls. Its title and
        # status bands do not consume thick side borders around app content.
        canvas.rounded_rect(shell.x, shell.y, shell.width, shell.height, 14, EDGE)
        canvas.rounded_rect(shell.x + 1, shell.y + 1, shell.width - 2, shell.height - 2, 13, CHROME)
        canvas.rect(c.x, 6, c.width, 40, (64, 96, 128))
        canvas.rect(c.x, c.y, c.width, c.height, WHITE)
        draw_content(canvas, c)
        canvas.rect(c.x, 46, c.width, 1, EDGE)
        sy = c.y + c.height
        canvas.rect(c.x, sy, c.width, 1, EDGE)
        canvas.rect(c.x, sy + 1, c.width, 24, (32, 64, 96))
        canvas.circle(shell.x + 14, 25, 3, FOCUS if self.focused else SUBTLE)
        available = shell.width - 43
        canvas.text(self.title[:max(1, available // 14)], shell.x + 27, 18, TEXT, scale=2, bold=True)
        label = "ACTIVE" if self.focused else "SPATIAL"
        if self.hovered == "move": label = "MOVE / DOWN TO STORE"
        elif self.hovered == "resize_right": label = "RESIZE"
        elif self.hovered == "close": label = "CLOSE"
        canvas.text(label, c.x + 10, sy + 9, SUBTLE, scale=1)
        # Clip all bands to the rounded shell, including callbacks that fill
        # their content rectangle. Only the perimeter receives the focus edge.
        canvas.pixels[self._clip_outside] = BLACK
        alpha = self._edge_alpha
        canvas.pixels[self._clip_edges] = np.rint(
            canvas.pixels[self._clip_edges]*alpha + np.asarray(BLACK,dtype=np.float32)*(1-alpha)
        ).astype(np.uint8)
        if self.focused:
            canvas.rect(shell.x + 14, shell.y, shell.width - 28, 1, FOCUS)
        for name, polygon in (self.controls().items() if self.focused and not self.external_controls else ()):
            selected = name == self.hovered or name == self.dragging
            x, y = polygon.min(axis=0)
            w, h = polygon.max(axis=0) - polygon.min(axis=0)
            x, y = int(x), int(y)
            canvas.pixels[y:y+40, x:x+40] = button_image(name, selected)
        return canvas.image()


class BoayoApplicationWindow:
    """Register an app-owned BOSIO window and handle BoAYo caption actions."""

    def __init__(self, wm, title, azimuth, elevation, width_deg, height_deg,
                 width=400, height=300, accent=ACCENT):
        self.wm = wm
        self.frame = BoayoAppFrame(width, height, title, accent)
        self.frame.external_controls = True
        info = wm.create_window(title, azimuth=azimuth, elevation=elevation,
                                width_deg=width_deg, height_deg=height_deg,
                                surface_width=width, surface_height=height,
                                decorated=False, workspace={"role": "app", "state": "open"},
                                shape=self.frame.shape_rects())
        self.window_id = info["window_id"] if isinstance(info, dict) else int(info)
        self.publisher = SurfacePublisher(wm, self.window_id)
        self.azimuth, self.elevation = float(azimuth), float(elevation)
        self.width_deg, self.height_deg = float(width_deg), float(height_deg)
        self.focused = bool(info.get("focused", True)) if isinstance(info, dict) else True
        self.drag = None
        self.last_drag_pose = None
        self.pressed_zone = None
        self.closed = False
        self.minimized = False
        self.minimize_elevation = -36.0
        self.restore_geometry = None
        self._transition = None
        self._content = None
        self._cancel_serial = 0
        self.frame.focused = self.focused
        self.frame.compact = self.width_deg < 24
        self._keyboard_index = -1
        self.caption = CaptionControls(self)
        self._published_shape = None
        self._sync_shape()

    def _sync_shape(self):
        shape = self.frame.shape_rects()
        if shape != self._published_shape:
            self.wm.configure_window(self.window_id, shape=shape)
            self._published_shape = shape

    @property
    def state(self):
        """Return a stable snapshot; angular resize does not resize RGB pixels."""
        return BoayoWindowState(
            self.window_id, self.azimuth, self.elevation,
            self.width_deg, self.height_deg,
            self.frame.width, self.frame.height,
            self.frame.content.width, self.frame.content.height,
            self.focused, self.closed, self.minimized,
            "minimizing" if self._transition else (self.drag[0] if self.drag else "idle"),
        )

    def _geometry(self):
        return dict(azimuth=self.azimuth, elevation=self.elevation,
                    width_deg=self.width_deg, height_deg=self.height_deg)

    def _publish(self, phase="open", **extra):
        self.wm.configure_window(self.window_id, workspace={"role": "app", "state": phase,
            "restore": self.restore_geometry or self._geometry(), **extra})

    def minimize(self, normal_geometry=None):
        if self.closed or self.minimized or self._transition:
            return
        self.restore_geometry = dict(normal_geometry or self._geometry())
        self.cancel_drag()
        self._transition = (time.monotonic(), self._geometry())
        self._publish("minimizing", dock_azimuth=self.azimuth)

    def restore(self, azimuth=None, elevation=None):
        if self.closed:
            return
        geometry = dict(self.restore_geometry or self._geometry())
        if azimuth is not None and elevation is not None:
            geometry.update(azimuth=(float(azimuth) + 180) % 360 - 180,
                            elevation=max(-85, min(85, float(elevation))))
        self.azimuth, self.elevation = geometry["azimuth"], geometry["elevation"]
        self.width_deg, self.height_deg = geometry["width_deg"], geometry["height_deg"]
        self.minimized = False
        self._transition = None
        self.wm.configure_window(self.window_id, mapped=True, **geometry)
        self.wm.focus_window(self.window_id)
        self.focused = self.frame.focused = True
        self._publish()
        self.redraw()

    def close(self):
        if not self.closed:
            self.cancel_drag()
            self.caption.close()
            self.wm.destroy_window(self.window_id)
            self.closed = True

    def tick(self, now=None):
        self.caption.sync()
        if self._transition is None:
            return
        started, geometry = self._transition
        progress = min(1.0, ((time.monotonic() if now is None else now) - started) / .22)
        if progress >= 1:
            self._transition = None
            self.minimized = True
            self.focused = self.frame.focused = False
            self.wm.configure_window(self.window_id, mapped=False)
            self._publish("minimized", dock_azimuth=geometry["azimuth"])
        # Preserve geometry and RGB during the short transition. Shrinking and
        # fading the whole window would invalidate all its cached projected tiles.
        # The storage card supplies the visual state once the window is hidden.

    def redraw(self, fade=0):
        if not self.closed:
            self._sync_shape()
            self.caption.sync()
        if self._content is None or self.minimized or self.closed:
            return
        def draw(canvas, rect):
            canvas.pixels[rect.y:rect.y + rect.height, rect.x:rect.x + rect.width] = self._content
        image = self.frame.render(draw)
        if fade:
            image = (image.astype(np.float32) * (1 - fade) + np.asarray(BLACK) * fade).astype(np.uint8)
        self.publisher.publish(image)

    def finish_drag(self, azimuth=None, elevation=None, cancelled=False):
        if self.drag is None:
            return
        zone, _, _, base_az, base_el, base_w, base_h, _, _ = self.drag
        if not cancelled and azimuth is not None and elevation is not None:
            self.apply_gaze_drag(azimuth, elevation)
        if not cancelled and zone == "move" and elevation is not None and elevation <= self.minimize_elevation:
            self.minimize(dict(azimuth=base_az, elevation=base_el, width_deg=base_w, height_deg=base_h))
        else:
            self.cancel_drag()
            self._publish()
        self.redraw()

    @staticmethod
    def _gaze_at_surface(azimuth, elevation, width_deg, height_deg, u, v):
        """Recover the fixed world gaze where a caption drag started."""
        az, el = math.radians(azimuth), math.radians(elevation)
        center = np.asarray((math.cos(el) * math.sin(az), math.sin(el),
                             -math.cos(el) * math.cos(az)))
        right = np.asarray((math.cos(az), 0.0, math.sin(az)))
        up = np.cross(right, center)
        ray = (center + (2 * u - 1) * math.tan(math.radians(width_deg / 2)) * right +
               (1 - 2 * v) * math.tan(math.radians(height_deg / 2)) * up)
        ray /= np.linalg.norm(ray)
        return math.degrees(math.atan2(ray[0], -ray[2])), math.degrees(math.asin(ray[1]))

    def apply_gaze_drag(self, azimuth, elevation):
        """Move or resize against the original world gaze, even off-window."""
        if self.drag is None:
            return False
        pose = float(azimuth), float(elevation)
        if self.last_drag_pose is not None and all(abs(a - b) < .01 for a, b in zip(pose, self.last_drag_pose)):
            return False
        self.last_drag_pose = pose
        zone, _, _, base_az, base_el, base_w, base_h, start_az, start_el = self.drag
        delta_az = (pose[0] - start_az + 180) % 360 - 180
        delta_el = pose[1] - start_el
        if zone == "move":
            self.azimuth = (base_az + delta_az + 180) % 360 - 180
            self.elevation = max(-89.5, min(89.5, base_el + delta_el))
            self.wm.configure_window(self.window_id, azimuth=self.azimuth, elevation=self.elevation)
        else:
            factor = -1 if zone == "resize_left" else 1
            new_w = max(10, min(100, base_w + factor * delta_az))
            new_h = max(8, min(80, base_h - delta_el))
            # Keep the opposite horizontal edge and the top edge in place.
            self.azimuth = (base_az + factor * (new_w - base_w) / 2 + 180) % 360 - 180
            self.elevation = max(-89.5, min(89.5, base_el - (new_h - base_h) / 2))
            self.width_deg, self.height_deg = new_w, new_h
            self.frame.compact = new_w < 24
            self.wm.configure_window(self.window_id, azimuth=self.azimuth,
                                     elevation=self.elevation, width_deg=new_w, height_deg=new_h)
        self._publish("moving" if zone == "move" else "resizing",
                      drop_candidate=zone == "move" and pose[1] <= self.minimize_elevation)
        self.caption.sync()
        return True

    def cancel_drag(self):
        was_dragging = self.drag is not None
        self.drag = None
        self.last_drag_pose = None
        self.pressed_zone = None
        self.frame.dragging = None
        if was_dragging and hasattr(self.wm, "release_pointer"):
            self.wm.release_pointer()

    def present(self, draw_content):
        """Draw content with a BoayoSurface callback; SDK adds the caption."""
        if self.closed:
            return
        image = self.frame.render(draw_content)
        rect = self.frame.content
        self._content = image[rect.y:rect.y + rect.height, rect.x:rect.x + rect.width].copy()
        if not self.minimized and not self._transition:
            self.publisher.publish(image)
            self.caption.sync()

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
        event = self.caption.route(event)
        if event.get("window_id") != self.window_id or self.closed:
            return None
        kind = event.get("type")
        if kind == "focus":
            state = self.wm.get_state() if self.caption.ids else None
            self.focused = ((state.get("focused_window") == self.window_id or
                             self.caption.owns(state.get("focused_window")))
                            if isinstance(state, dict) and "focused_window" in state
                            else bool(event.get("focused")))
            self.frame.focused = self.focused
            if not self.focused:
                self.cancel_drag()
                self.frame.hovered = None
            self.redraw()
            return None
        if kind == "pointer_leave":
            if self.pressed_zone == "close":
                self.pressed_zone = None
            self.frame.hovered = None
            self.redraw()
            return None
        if kind == "window_action":
            action = event.get("action")
            if action == "minimize":
                self.minimize()
            elif action == "restore":
                self.restore(event.get("azimuth"), event.get("elevation"))
            elif action == "close":
                self.close()
            return None
        if kind == "pointer_cancel":
            self.finish_drag(cancelled=True)
            self.pressed_zone = None
            return None
        if kind == "key" and event.get("pressed"):
            key = event.get("key")
            if key == "tab" and self.focused:
                names = list(self.frame.controls())
                self._keyboard_index = (self._keyboard_index + 1) % len(names)
                self.frame.hovered = names[self._keyboard_index]
                self.redraw()
            elif key == "escape":
                self.finish_drag(cancelled=True)
                self.pressed_zone = None
            return None
        if self.minimized or self._transition:
            return None
        if kind == "pointer_button" and event.get("button") == "left":
            zone = (event["_caption_control"] if "_caption_control" in event else
                    self.frame.hit_test(event.get("u", -1), event.get("v", -1)))
            if event.get("pressed"):
                self._cancel_serial = event.get("cancel_serial", self._cancel_serial)
                self.pressed_zone = zone
                if zone in ("move", "resize_left", "resize_right"):
                    start_az, start_el = self._gaze_at_surface(
                        self.azimuth, self.elevation, self.width_deg, self.height_deg,
                        float(event["u"]), float(event["v"]),
                    )
                    if "azimuth" in event and "elevation" in event:
                        start_az, start_el = event["azimuth"], event["elevation"]
                    self.drag = (zone, float(event["u"]), float(event["v"]),
                                 self.azimuth, self.elevation, self.width_deg, self.height_deg,
                                 start_az, start_el)
                    self.last_drag_pose = None
                    self.frame.dragging = zone
                    if hasattr(self.wm, "capture_pointer"):
                        self.wm.capture_pointer(event.get("_caption_source", self.window_id))
                    self._publish("moving" if zone == "move" else "resizing")
                    self.redraw()
                return zone
            if self.drag is not None:
                self.finish_drag(event.get("azimuth"), event.get("elevation"))
            elif zone == "close" and self.pressed_zone == "close":
                self.close()
            self.pressed_zone = None
            return zone
        if kind == "pointer_motion" and self.drag is None:
            hovered = (event["_caption_control"] if "_caption_control" in event else
                       self.frame.hit_test(event.get("u", -1), event.get("v", -1)))
            if hovered != self.frame.hovered:
                self.frame.hovered = hovered
                self.redraw()
        if kind == "pointer_motion" and self.drag is not None:
            if "azimuth" in event and "elevation" in event:
                return self.apply_gaze_drag(event["azimuth"], event["elevation"])
            zone, u0, v0, az, el, wdeg, hdeg, _, _ = self.drag
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
