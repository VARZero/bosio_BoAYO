"""Lightweight RGB drawing primitives used by the BoAYo desktop shell."""

from __future__ import annotations

import numpy as np

try:
    from bosio_window_gui import FONT_5X7
except ImportError:
    from .bosio_window_gui import FONT_5X7

BLACK = (3, 5, 8)
WHITE = (250, 250, 249)
INK = (22, 29, 40)
MUTED = (105, 116, 132)
PANEL = (239, 242, 246)
ACCENT = (44, 112, 246)


def scaled_polygon(points, scale):
    points = np.asarray(points, dtype=np.float32)
    center = points.mean(axis=0)
    return center + (points - center) * float(scale)


def point_in_polygon(x, y, points):
    inside = False
    previous = points[-1]
    for current in points:
        x0, y0 = previous
        x1, y1 = current
        if (y0 > y) != (y1 > y):
            crossing = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def rounded_polygon_path(points, radius, steps=5):
    points = np.asarray(points, dtype=np.float32)
    path = []
    for index, vertex in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        before = vertex + (previous - vertex) * min(0.45, radius / max(np.linalg.norm(previous - vertex), 1.0))
        after = vertex + (following - vertex) * min(0.45, radius / max(np.linalg.norm(following - vertex), 1.0))
        for t in np.linspace(0.0, 1.0, steps, endpoint=False):
            path.append((1 - t) ** 2 * before + 2 * (1 - t) * t * vertex + t ** 2 * after)
    return np.asarray(path, dtype=np.float32)


class BoayoSurface:
    def __init__(self, width=640, height=360, background=BLACK):
        self.width = int(width)
        self.height = int(height)
        self.pixels = np.empty((self.height, self.width, 3), dtype=np.uint8)
        self.clear(background)

    def clear(self, color=BLACK):
        self.pixels[:] = color

    def rect(self, x, y, width, height, color, fill=True, stroke=1):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.width, int(x + width)), min(self.height, int(y + height))
        if x0 >= x1 or y0 >= y1:
            return
        if fill:
            self.pixels[y0:y1, x0:x1] = color
            return
        s = max(1, int(stroke))
        self.pixels[y0:min(y1, y0 + s), x0:x1] = color
        self.pixels[max(y0, y1 - s):y1, x0:x1] = color
        self.pixels[y0:y1, x0:min(x1, x0 + s)] = color
        self.pixels[y0:y1, max(x0, x1 - s):x1] = color

    def rounded_rect(self, x, y, width, height, radius, color):
        x, y, width, height, radius = map(int, (x, y, width, height, radius))
        radius = max(0, min(radius, width // 2, height // 2))
        self.rect(x + radius, y, width - radius * 2, height, color)
        self.rect(x, y + radius, width, height - radius * 2, color)
        if radius == 0:
            return
        yy, xx = np.ogrid[:radius, :radius]
        circle = (xx - radius + 0.5) ** 2 + (yy - radius + 0.5) ** 2 <= radius ** 2
        corners = (
            (slice(y, y + radius), slice(x, x + radius), circle),
            (slice(y, y + radius), slice(x + width - radius, x + width), np.fliplr(circle)),
            (slice(y + height - radius, y + height), slice(x, x + radius), np.flipud(circle)),
            (slice(y + height - radius, y + height), slice(x + width - radius, x + width), np.flipud(np.fliplr(circle))),
        )
        for ys, xs, mask in corners:
            block = self.pixels[ys, xs]
            if block.shape[:2] == mask.shape:
                block[mask] = color

    def polygon(self, points, color):
        points = np.asarray(points, dtype=np.float32)
        x0 = max(0, int(np.floor(points[:, 0].min())))
        x1 = min(self.width, int(np.ceil(points[:, 0].max())) + 1)
        y0 = max(0, int(np.floor(points[:, 1].min())))
        y1 = min(self.height, int(np.ceil(points[:, 1].max())) + 1)
        if x0 >= x1 or y0 >= y1:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1]
        inside = np.zeros(xx.shape, dtype=bool)
        previous = points[-1]
        for current in points:
            px, py = previous
            cx, cy = current
            crossing = ((py > yy) != (cy > yy)) & (xx < (cx - px) * (yy - py) / ((cy - py) or 1e-6) + px)
            inside ^= crossing
            previous = current
        self.pixels[y0:y1, x0:x1][inside] = color

    def rounded_polygon(self, points, radius, color):
        self.polygon(rounded_polygon_path(points, radius), color)

    def circle(self, cx, cy, radius, color):
        y0, y1 = max(0, int(cy - radius)), min(self.height, int(cy + radius + 1))
        x0, x1 = max(0, int(cx - radius)), min(self.width, int(cx + radius + 1))
        yy, xx = np.ogrid[y0:y1, x0:x1]
        self.pixels[y0:y1, x0:x1][(xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2] = color

    def text(self, value, x, y, color=INK, scale=2, bold=False):
        cursor = int(x)
        scale = max(1, int(scale))
        for char in str(value).upper():
            glyph = FONT_5X7.get(char, FONT_5X7[" "])
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit == "#":
                        self.rect(cursor + col * scale, y + row * scale, scale + int(bold), scale, color)
            cursor += (7 if bold else 6) * scale

    def card(self, x, y, width, height, title, value, accent=ACCENT):
        self.rounded_rect(x, y, width, height, 12, PANEL)
        self.circle(x + 20, y + 21, 6, accent)
        self.text(title, x + 34, y + 13, MUTED, scale=2)
        self.text(value, x + 18, y + 46, INK, scale=3, bold=True)

    def progress(self, x, y, width, ratio, color=ACCENT):
        ratio = max(0.0, min(1.0, float(ratio)))
        self.rounded_rect(x, y, width, 10, 5, (218, 224, 232))
        if ratio:
            self.rounded_rect(x, y, max(10, int(width * ratio)), 10, 5, color)

    def image(self):
        return np.ascontiguousarray(self.pixels)


VoayoSurface = BoayoSurface
