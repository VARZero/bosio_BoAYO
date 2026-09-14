"""Desktop reference view of a BOSIO 20-face, 211-tile scene.

This samples the same face/tile/triangular-cell hierarchy used by the output
core.  It is intended for honest visual previews, not as a replacement for
capture from the FPGA HDMI output.
"""

from __future__ import annotations

import math

import numpy as np

try:
    from bosio_geometry_v2 import INVERSES, locate
except ImportError:
    from .bosio_geometry_v2 import INVERSES, locate


def _basis(yaw, pitch, roll=0.0):
    az, el, rl = np.radians([yaw, pitch, roll])
    center = np.asarray((math.cos(el) * math.sin(az), math.sin(el), -math.cos(el) * math.cos(az)))
    right0 = np.asarray((math.cos(az), 0.0, math.sin(az)))
    up0 = np.cross(right0, center)
    right = right0 * math.cos(rl) + up0 * math.sin(rl)
    up = up0 * math.cos(rl) - right0 * math.sin(rl)
    return center, right, up


def _rgb332(rgb):
    rgb = np.asarray(rgb, dtype=np.uint8)
    index = (rgb[..., 0] & 224) | ((rgb[..., 1] >> 3) & 28) | (rgb[..., 2] >> 6)
    red = (index.astype(np.uint16) >> 5) * 255 // 7
    green = ((index.astype(np.uint16) >> 2) & 7) * 255 // 7
    blue = (index.astype(np.uint16) & 3) * 255 // 3
    return np.stack((red, green, blue), axis=-1).astype(np.uint8)


def render_bosio_view(scene_rgb, m=16, yaw=0.0, pitch=0.0, roll=0.0,
                      fov_h=60.0, fov_v=45.0, width=1280, height=720):
    """Reconstruct one viewport by sampling BOSIO triangular cells."""
    scene = np.asarray(scene_rgb, dtype=np.uint8)
    if scene.shape != (20, 211, int(m) * int(m), 3):
        raise ValueError("invalid BOSIO scene shape")
    width, height = int(width), int(height)
    center, right, up = _basis(yaw, pitch, roll)
    xs = (2.0 * (np.arange(width) + 0.5) / width - 1.0) * math.tan(math.radians(fov_h / 2))
    output = np.empty((height, width, 3), dtype=np.uint8)
    for y0 in range(0, height, 24):
        y1 = min(height, y0 + 24)
        ys = (1.0 - 2.0 * (np.arange(y0, y1) + 0.5) / height) * math.tan(math.radians(fov_v / 2))
        rays = center + xs[None, :, None] * right + ys[:, None, None] * up
        rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
        barycentric = np.einsum("fij,hwj->hwfi", INVERSES, rays)
        valid = np.all(barycentric >= -1e-8, axis=-1)
        faces = np.argmax(valid, axis=-1)
        selected = np.take_along_axis(barycentric, faces[..., None, None], axis=2)[..., 0, :]
        selected /= selected.sum(axis=-1, keepdims=True)
        tiles, cells = locate(selected, m)
        output[y0:y1] = scene[faces, tiles, cells]
    return _rgb332(output)
