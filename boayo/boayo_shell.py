"""BoAYo desktop shell: internal windows, gaze hit testing, and RGB composition.

BOSIO only receives the finished scene.  Caption controls intentionally live
inside this shell's black allocation, outside the white application content.
"""

from __future__ import annotations

import math
import json
import os
import shlex
import subprocess
from dataclasses import dataclass

import numpy as np

try:
    from boayo_ui import ACCENT, BLACK, INK, MUTED, PANEL, WHITE, BoayoSurface, point_in_polygon, scaled_polygon
    from bosio_geometry_v2 import cell_rays
except ImportError:
    from .boayo_ui import ACCENT, BLACK, INK, MUTED, PANEL, WHITE, BoayoSurface, point_in_polygon, scaled_polygon
    from .bosio_geometry_v2 import cell_rays


@dataclass
class WindowRect:
    x: float = 68
    y: float = 28
    width: float = 504
    height: float = 252


class BoayoShell:
    MIN_WIDTH = 300
    MIN_HEIGHT = 170

    def __init__(self, width=640, height=360):
        self.width = int(width)
        self.height = int(height)
        self.surface = BoayoSurface(width, height)
        self.window = WindowRect(
            x=self.width * 0.106,
            y=self.height * 0.078,
            width=self.width * 0.788,
            height=self.height * 0.70,
        )
        self.visible = True
        self.hovered = None
        self.pressed = None
        self.selected_card = 0
        self.focus_amount = {name: 0.0 for name in ("resize_left", "close", "move", "resize_right")}
        self.pointer = (-1.0, -1.0)
        self.pointer_source = None
        self._drag_origin = None
        self._window_origin = None
        self.auto_hide = False

    def caption_polygons(self):
        r = self.window
        bottom, left, right = r.y + r.height, r.x, r.x + r.width
        return {
            "resize_left": np.asarray(((left - 28, bottom + 38), (left - 28, bottom + 6), (left + 4, bottom + 38)), dtype=np.float32),
            "close": np.asarray(((left + 20, bottom + 10), (left + 58, bottom + 10), (left + 39, bottom + 42)), dtype=np.float32),
            "move": np.asarray(((left + 70, bottom + 12), (left + 126, bottom + 12), (left + 134, bottom + 38), (left + 62, bottom + 38)), dtype=np.float32),
            "resize_right": np.asarray(((right - 4, bottom + 38), (right + 28, bottom + 6), (right + 28, bottom + 38)), dtype=np.float32),
        }

    def hit_test(self, x, y):
        for name, points in self.caption_polygons().items():
            if point_in_polygon(float(x), float(y), scaled_polygon(points, 1.16)):
                return name
        r = self.window
        if r.x <= x <= r.x + r.width and r.y <= y <= r.y + r.height:
            return "content"
        return None

    def pointer_motion(self, x, y):
        x, y = float(x), float(y)
        self.pointer = (x, y)
        if self.pressed in ("move", "resize_left", "resize_right"):
            self._apply_drag(x, y)
        self.hovered = self.hit_test(x, y) if self.visible else None
        return self.hovered

    def mouse_motion(self, x, y):
        self.pointer_source = "mouse"
        return self.pointer_motion(x, y)

    def _draw_cursor(self, canvas):
        if self.pointer_source != "mouse":
            return
        x, y = self.pointer
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        canvas.circle(x, y, 9, (20, 28, 42))
        canvas.circle(x, y, 6, (250, 250, 249))
        canvas.rect(x + 5, y - 1, 12, 3, (20, 28, 42))
        canvas.rect(x - 1, y + 5, 3, 12, (20, 28, 42))

    def pointer_normalized(self, u, v):
        return self.pointer_motion(float(u) * self.width, float(v) * self.height)

    def pointer_button(self, pressed):
        pressed = bool(pressed)
        if pressed:
            self.pressed = self.hovered
            if self.pressed in ("move", "resize_left", "resize_right"):
                self._drag_origin = self.pointer
                self._window_origin = WindowRect(**vars(self.window))
            elif self.pressed == "content":
                self._select_content(*self.pointer)
            return self.pressed
        released = self.pressed
        if released == "close" and self.hovered == "close":
            self.visible = False
        self.pressed = None
        self._drag_origin = None
        self._window_origin = None
        return released

    def scroll(self, delta):
        return False

    def _select_content(self, x, y):
        r = self.window
        inner_x = r.x + 24
        available = r.width - 48
        gap = 10
        card_width = (available - gap * 2) / 3
        if r.y + 72 <= y <= r.y + 160 and inner_x <= x <= inner_x + available:
            self.selected_card = min(2, max(0, int((x - inner_x) / (card_width + gap))))

    def _apply_drag(self, x, y):
        if self._drag_origin is None:
            return
        dx, dy = x - self._drag_origin[0], y - self._drag_origin[1]
        base = self._window_origin
        if self.pressed == "move":
            nx = min(self.width - base.width - 32, max(32, base.x + dx))
            ny = min(self.height - base.height - 58, max(12, base.y + dy))
            self.window.x, self.window.y = nx, ny
        elif self.pressed == "resize_left":
            right = base.x + base.width
            nx = min(right - self.MIN_WIDTH, max(32, base.x + dx))
            self.window.x = nx
            self.window.width = right - nx
            self.window.height = min(self.height - base.y - 58, max(self.MIN_HEIGHT, base.height + dy))
        elif self.pressed == "resize_right":
            self.window.width = min(self.width - base.x - 32, max(self.MIN_WIDTH, base.width + dx))
            self.window.height = min(self.height - base.y - 58, max(self.MIN_HEIGHT, base.height + dy))

    def tick(self, seconds):
        blend = min(1.0, max(0.0, float(seconds)) * 10.0)
        changed = False
        for name, value in self.focus_amount.items():
            target = 1.0 if name == self.hovered else 0.0
            updated = value + (target - value) * blend
            changed |= abs(updated - value) > 0.002
            self.focus_amount[name] = updated
        return changed

    @staticmethod
    def _mix(dark, light, amount):
        return tuple(int(a + (b - a) * amount) for a, b in zip(dark, light))

    def render(self):
        canvas = self.surface
        canvas.clear(BLACK)
        if not self.visible:
            return canvas.image()
        r = self.window
        canvas.rounded_rect(r.x + 3, r.y + 5, r.width, r.height, 20, (13, 16, 21))
        canvas.rounded_rect(r.x, r.y, r.width, r.height, 18, WHITE)
        self._draw_content(canvas, r)
        for name, points in self.caption_polygons().items():
            amount = self.focus_amount[name]
            scale = 1.0 + 0.12 * amount
            # RGB332 has only two blue bits. Equal-looking source RGB values
            # must land on balanced palette levels; (64,64,64) decodes to a
            # dark blue-gray instead of the green cast produced by 92/99/110.
            color = self._mix((64, 64, 64), (238, 244, 250), amount)
            if name == "close":
                color = self._mix((116, 30, 30), (255, 96, 78), amount)
            canvas.rounded_polygon(scaled_polygon(points, scale), 6 + amount * 2, color)
        self._draw_cursor(canvas)
        return canvas.image()

    def _draw_content(self, canvas, r):
        x, y, width, height = map(int, (r.x, r.y, r.width, r.height))
        canvas.text("BOAYO", x + 24, y + 20, INK, scale=3, bold=True)
        canvas.text("GAZE DESKTOP", x + 128, y + 28, MUTED, scale=2)
        inner_x = x + 24
        available = width - 48
        gap = 10
        card_width = (available - gap * 2) // 3
        cards = (("SYSTEM", "READY"), ("DISPLAY", "60 FPS"), ("FOCUS", "GAZE"))
        for index, (title, value) in enumerate(cards):
            accent = (255, 92, 73) if index == self.selected_card else ACCENT
            canvas.card(inner_x + index * (card_width + gap), y + 70, card_width, 90, title, value, accent)
        if height >= 218:
            canvas.rounded_rect(inner_x, y + 176, available, height - 194, 12, PANEL)
            canvas.text("CONTENT AREA", inner_x + 18, y + 190, MUTED, scale=2)
            if height >= 246:
                canvas.progress(inner_x + 18, y + 218, available - 36, 0.68, ACCENT)


class BoayoLauncherShell(BoayoShell):
    """Gaze-first launcher surface without caption controls."""

    def __init__(self, width=640, height=360, apps_path=None):
        super().__init__(width, height)
        self.window = WindowRect(self.width * 0.08, self.height * 0.10,
                                 self.width * 0.84, self.height * 0.70)
        self.apps_path = apps_path or os.path.join(os.path.dirname(__file__), "apps.json")
        self.apps = self._load_apps()
        self.selected_app = None
        self.active_app = None
        self.last_launch = None
        self.launch_pose = (0.0, 0.0)
        self.scroll_offset = 0
        self._cached_render_key = None

    def render_key(self):
        """Visible launcher state; gaze position belongs to the BOSIO window."""
        return (self.visible, id(self.selected_app), id(self.active_app),
                self.scroll_offset, self.pointer_source,
                self.pointer if self.pointer_source == "mouse" else None)

    def caption_polygons(self):
        return {}

    def _load_apps(self):
        try:
            with open(self.apps_path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
            apps = []
            for app in data.get("apps", []):
                if not app.get("enabled", True):
                    continue
                command = app.get("command")
                if not command:
                    continue
                argv = self._command_argv(command)
                target = argv[1] if argv and argv[0].endswith(("python", "python3")) and len(argv) > 1 else (argv[0] if argv else "")
                if target and (not os.path.isabs(target) or os.path.isfile(target)):
                    apps.append(app)
            return apps
        except (OSError, ValueError, TypeError):
            return []

    def _select_content(self, x, y):
        # Each visible launcher row (icon + label) is one click target.
        r = self.window
        left = r.x + r.width * 0.34
        right = r.x + r.width - 18
        top = r.y + 22
        row_height = 54
        row = int((y - top) / row_height)
        index = self.scroll_offset + row
        if left <= x <= right and 0 <= row and 0 <= index < len(self.apps):
            self.selected_app = self.apps[index]

    def pointer_button(self, pressed):
        result = super().pointer_button(pressed)
        if not pressed and result == "content" and self.selected_app:
            self.launch_app(self.selected_app)
        return result

    @staticmethod
    def _command_argv(command):
        argv = shlex.split(str(command))
        if argv and argv[0].endswith(".py"):
            argv.insert(0, os.environ.get("PYTHON", "python3"))
        return argv

    def launch_app(self, app):
        if not app:
            return False
        command = app.get("command")
        if command:
            argv = self._command_argv(command)
            target = argv[1] if argv and argv[0].endswith(("python", "python3")) and len(argv) > 1 else (argv[0] if argv else "")
            if argv and (not os.path.isabs(target) or os.path.isfile(target)):
                try:
                    env = os.environ.copy()
                    env["BOAYO_APP_AZIMUTH"] = str(self.launch_pose[0])
                    env["BOAYO_APP_ELEVATION"] = str(self.launch_pose[1])
                    sdk_dir = os.path.dirname(os.path.abspath(__file__))
                    stack_dir = os.path.dirname(sdk_dir)
                    env["PYTHONPATH"] = os.pathsep.join(
                        part for part in (sdk_dir, stack_dir, env.get("PYTHONPATH")) if part
                    )
                    subprocess.Popen(argv, start_new_session=True, env=env)
                    self.last_launch = app.get("name", app.get("id", "app"))
                    self.active_app = app
                    return True
                except (OSError, ValueError):
                    pass
        return False

    def scroll(self, delta):
        if self.active_app is not None or len(self.apps) < 2:
            return False
        before = self.scroll_offset
        self.scroll_offset = max(0, min(len(self.apps) - 1,
                                        self.scroll_offset - (1 if delta > 0 else -1)))
        return before != self.scroll_offset

    def render(self):
        key = self.render_key()
        if key == self._cached_render_key:
            return self.surface.image()
        canvas = self.surface
        if self.active_app is not None:
            canvas.clear(BLACK)
            self._cached_render_key = key
            return canvas.image()
        canvas.clear(BLACK)
        if not self.visible:
            self._cached_render_key = key
            return canvas.image()
        r = self.window
        canvas.rounded_rect(r.x + 3, r.y + 5, r.width, r.height, 20, (13, 16, 21))
        canvas.rounded_rect(r.x, r.y, r.width, r.height, 18, WHITE)
        x, y, width, height = map(int, (r.x, r.y, r.width, r.height))
        split = x + int(width * 0.34)
        canvas.rounded_rect(x + 10, y + 10, split - x - 16, height - 20, 14, PANEL)
        canvas.rect(split - 3, y + 22, 1, height - 44, (213, 220, 229))
        # Device status: battery is intentionally only a thin indicator.
        canvas.rounded_rect(x + 24, y + 30, split - x - 44, 7, 4, (211, 220, 230))
        canvas.rounded_rect(x + 24, y + 30, int((split - x - 44) * 0.82), 7, 4, (57, 184, 121))
        # Large proportional volume tile.
        vx, vy, vw, vh = x + 24, y + 66, split - x - 44, 68
        canvas.rounded_rect(vx, vy, vw, vh, 16, (216, 224, 233))
        canvas.rounded_rect(vx, vy, int(vw * 0.64), vh, 16, ACCENT)
        canvas.text(">))", vx + 15, vy + 23, WHITE, scale=3, bold=True)
        # Re-center action remains available without a caption bar.
        canvas.rounded_rect(x + 24, y + height - 62, split - x - 44, 34, 8, WHITE)
        canvas.text("CENTER", x + 30, y + height - 55, INK, scale=3, bold=True)
        list_x, list_y = split + 20, y + 22
        row_h = 54
        visible = max(1, min(5, int((height - 38) / row_h)))
        for row in range(visible):
            index = self.scroll_offset + row
            if index >= len(self.apps):
                break
            app = self.apps[index]
            bx, by = list_x, list_y + row * row_h
            selected = app is self.selected_app
            if selected:
                canvas.rounded_rect(bx, by, x + width - bx - 18, row_h - 5, 9, (228, 239, 255))
            color = tuple(int(app.get("color", "#347CFF").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if isinstance(app.get("color"), str) and len(app.get("color", "").lstrip("#")) == 6 else ACCENT
            canvas.rounded_rect(bx + 8, by + 5, 38, 38, 11, color)
            label = str(app.get("name", app.get("id", "APP")))[:9]
            canvas.text(label, bx + 56, by + 10, INK, scale=4, bold=True)
        if len(self.apps) > visible:
            canvas.text("WHEEL", list_x + 8, y + height - 27, MUTED, scale=2, bold=True)
        self._draw_cursor(canvas)
        self._cached_render_key = key
        return canvas.image()


def _direction(azimuth, elevation):
    az, el = np.radians([azimuth, elevation])
    return np.asarray((math.cos(el) * math.sin(az), math.sin(el), -math.cos(el) * math.cos(az)), dtype=np.float32)


def _basis(azimuth, elevation):
    center = _direction(azimuth, elevation)
    az = math.radians(azimuth)
    right = np.asarray((math.cos(az), 0.0, math.sin(az)), dtype=np.float32)
    return center, right, np.cross(right, center)


class BoayoScene:
    """Maps the complete BoAYo shell canvas directly into BOSIO scene cells."""

    def __init__(self, shell=None, m=16, azimuth=0.0, elevation=0.0, width_deg=48.0, height_deg=27.0):
        self.shell = shell or BoayoShell()
        self.m = int(m)
        self.azimuth, self.elevation = float(azimuth), float(elevation)
        self.width_deg, self.height_deg = float(width_deg), float(height_deg)
        self.rays = cell_rays(self.m).astype(np.float32)
        self.rgb = np.empty((*self.rays.shape[:-1], 3), dtype=np.uint8)
        self._build_map()

    def _build_map(self):
        center, right, up = _basis(self.azimuth, self.elevation)
        dot = self.rays @ center
        x = (self.rays @ right) / np.maximum(dot, 1e-8) / math.tan(math.radians(self.width_deg / 2))
        y = (self.rays @ up) / np.maximum(dot, 1e-8) / math.tan(math.radians(self.height_deg / 2))
        self.mask = (dot > 0) & (np.abs(x) <= 1) & (np.abs(y) <= 1)
        self.destination = np.where(self.mask)
        self.fx = np.clip((x[self.mask] + 1) * 0.5 * (self.shell.width - 1), 0, self.shell.width - 1).astype(np.float32)
        self.fy = np.clip((1 - y[self.mask]) * 0.5 * (self.shell.height - 1), 0, self.shell.height - 1).astype(np.float32)

    def _bilinear(self, canvas, fx, fy):
        fx = np.clip(fx, 0, self.shell.width - 1)
        fy = np.clip(fy, 0, self.shell.height - 1)
        x0, y0 = np.floor(fx).astype(np.int32), np.floor(fy).astype(np.int32)
        x1, y1 = np.minimum(x0 + 1, self.shell.width - 1), np.minimum(y0 + 1, self.shell.height - 1)
        ax, ay = (fx - x0)[:, None], (fy - y0)[:, None]
        p00, p10 = canvas[y0, x0].astype(np.float32), canvas[y0, x1].astype(np.float32)
        p01, p11 = canvas[y1, x0].astype(np.float32), canvas[y1, x1].astype(np.float32)
        return p00 * (1 - ax) * (1 - ay) + p10 * ax * (1 - ay) + p01 * (1 - ax) * ay + p11 * ax * ay

    def sample(self, canvas):
        """Bilinear sample every cell and supersample only high-contrast edges."""
        sampled = self._bilinear(canvas, self.fx, self.fy)
        x0, y0 = np.floor(self.fx).astype(np.int32), np.floor(self.fy).astype(np.int32)
        x1, y1 = np.minimum(x0 + 1, self.shell.width - 1), np.minimum(y0 + 1, self.shell.height - 1)
        neighbors = np.stack((canvas[y0, x0], canvas[y0, x1], canvas[y1, x0], canvas[y1, x1]), axis=0).astype(np.int16)
        luminance = neighbors[..., 0] * 3 + neighbors[..., 1] * 6 + neighbors[..., 2]
        edge = np.ptp(luminance, axis=0) >= 216
        if np.any(edge):
            accum = np.zeros((int(np.count_nonzero(edge)), 3), dtype=np.float32)
            for oy in (-.375, -.125, .125, .375):
                for ox in (-.375, -.125, .125, .375):
                    accum += self._bilinear(canvas, self.fx[edge] + ox, self.fy[edge] + oy)
            sampled[edge] = accum * (1.0 / 16.0)
        return np.clip(np.rint(sampled), 0, 255).astype(np.uint8)

    def gaze(self, azimuth, elevation):
        self.shell.pointer_source = None
        direction = _direction(azimuth, elevation)
        center, right, up = _basis(self.azimuth, self.elevation)
        dot = float(direction @ center)
        if dot <= 0:
            if self.shell.auto_hide:
                self.shell.visible = False
            self.shell.pointer_motion(-1, -1)
            return None
        x = float(direction @ right) / dot / math.tan(math.radians(self.width_deg / 2))
        y = float(direction @ up) / dot / math.tan(math.radians(self.height_deg / 2))
        if abs(x) > 1 or abs(y) > 1:
            if self.shell.auto_hide:
                self.shell.visible = False
            self.shell.pointer_motion(-1, -1)
            return None
        if self.shell.auto_hide:
            self.shell.visible = True
        px = (x + 1) * 0.5 * self.shell.width
        py = (1 - y) * 0.5 * self.shell.height
        return self.shell.pointer_motion(px, py)

    def mouse_gaze(self, azimuth, elevation):
        direction = _direction(azimuth, elevation)
        center, right, up = _basis(self.azimuth, self.elevation)
        dot = float(direction @ center)
        if dot <= 0:
            self.shell.mouse_motion(-1, -1)
            return None
        x = float(direction @ right) / dot / math.tan(math.radians(self.width_deg / 2))
        y = float(direction @ up) / dot / math.tan(math.radians(self.height_deg / 2))
        if abs(x) > 1 or abs(y) > 1:
            self.shell.mouse_motion(-1, -1)
            return None
        px = (x + 1) * 0.5 * self.shell.width
        py = (1 - y) * 0.5 * self.shell.height
        return self.shell.mouse_motion(px, py)

    def render(self):
        self.rgb[:] = BLACK
        canvas = self.shell.render()
        self.rgb[self.destination] = self.sample(canvas)
        return self.rgb

    def pointer_button(self, pressed):
        return self.shell.pointer_button(pressed)

    def scroll(self, delta):
        return self.shell.scroll(delta)

    def tick(self, seconds):
        return self.shell.tick(seconds)


class BoayoWorkspace:
    """Composite several independent BoAYo windows at distinct sphere poses."""

    def __init__(self, m=16, base_azimuth=0.0, base_elevation=0.0, count=3, launcher=False, apps_path=None):
        count = max(1, int(count))
        offsets = ((0.0, 0.0), (-17.0, 2.0), (17.0, -2.0))
        self.items = []
        for index in range(count):
            daz, delv = offsets[index % len(offsets)]
            shell = (BoayoLauncherShell(640, 360, apps_path) if launcher and index == 0 else BoayoShell(640, 360))
            scene = BoayoScene(shell, m, base_azimuth + daz, base_elevation + delv,
                               42.0 if launcher else 26.0, 30.0 if launcher else 18.0)
            shell.selected_card = index % 3
            self.items.append((shell, scene))
        self.focused = 0
        self.mouse_pose = (base_azimuth, base_elevation)
        self.mouse_visible = False
        self._cursor_rays = cell_rays(m).reshape(-1, 3).astype(np.float32)

    def add_panel(self, azimuth, elevation, app=None):
        """Create a new execution panel at the current gaze direction."""
        # There is exactly one control/launcher panel. Running application
        # windows remain in the scene and are never removed here.
        m = self.items[0][1].m if self.items else 16
        self.items = [
            (old_shell, old_scene) for old_shell, old_scene in self.items
            if not (isinstance(old_shell, BoayoLauncherShell) and old_shell.active_app is None)
        ]
        shell = BoayoLauncherShell(640, 360)
        if app is not None:
            shell.selected_app = app
        scene = BoayoScene(shell, m, azimuth, elevation, 42.0, 30.0)
        self.items.append((shell, scene))
        self.focused = len(self.items) - 1
        return shell

    def recenter_launcher(self, azimuth, elevation):
        for index, (shell, scene) in enumerate(self.items):
            if isinstance(shell, BoayoLauncherShell) and shell.active_app is None:
                scene.azimuth, scene.elevation = float(azimuth), float(elevation)
                scene._build_map()
                self.items.append(self.items.pop(index))
                self.focused = len(self.items) - 1
                return scene
        return self.add_panel(azimuth, elevation)

    def gaze(self, azimuth, elevation):
        self.focused = None
        for index in range(len(self.items) - 1, -1, -1):
            shell, scene = self.items[index]
            hit = scene.gaze(azimuth, elevation)
            if hit is not None and self.focused is None:
                self.focused = index
        return self.focused

    def mouse_gaze(self, azimuth, elevation):
        self.mouse_pose = (float(azimuth), float(elevation))
        self.mouse_visible = False
        self.focused = None
        for index in range(len(self.items) - 1, -1, -1):
            shell, scene = self.items[index]
            hit = scene.mouse_gaze(azimuth, elevation)
            if hit is not None and self.focused is None:
                self.focused = index
        return self.focused

    def pointer_button(self, pressed):
        if self.focused is not None:
            shell = self.items[self.focused][0]
            if isinstance(shell, BoayoLauncherShell):
                shell.launch_pose = self.mouse_pose
            return shell.pointer_button(pressed)
        return None

    def scroll(self, delta):
        if self.focused is not None:
            return self.items[self.focused][0].scroll(delta)
        return False

    def tick(self, seconds):
        return any(shell.tick(seconds) for shell, _ in self.items)

    def render(self):
        output = np.zeros_like(self.items[0][1].rgb)
        for shell, scene in self.items:
            canvas = shell.render()
            source = scene.sample(canvas)
            visible = np.any(source != np.asarray(BLACK, dtype=np.uint8), axis=-1)
            indices = np.ravel_multi_index(scene.destination, output.shape[:-1])
            output.reshape(-1, 3)[indices[visible]] = source[visible]
        if self.mouse_visible:
            target = _direction(*self.mouse_pose)
            scores = self._cursor_rays @ target
            center = int(np.argmax(scores))
            flat = output.reshape(-1, 3)
            # Draw a compact high-contrast marker directly on the sphere, even
            # when the pointer is over the black background between panels.
            marker = scores >= math.cos(math.radians(1.4))
            flat[marker] = (238, 32, 92)
            flat[center] = (255, 255, 255)
        return output

