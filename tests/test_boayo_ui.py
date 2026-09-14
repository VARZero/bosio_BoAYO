import unittest
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "boayo"), str(ROOT / "vendor" / "bosio_SphericalWM" / "sw")]

from boayo_ui import PANEL, BoayoSurface
from boayo_shell import BoayoScene, BoayoShell
from bosio_view_simulator import render_bosio_view


class BoayoUITests(unittest.TestCase):
    def test_content_surface_and_components(self):
        surface = BoayoSurface(160, 100)
        surface.card(8, 8, 90, 70, "SYSTEM", "READY")
        surface.progress(12, 86, 120, 0.5)
        image = surface.image()
        self.assertEqual(image.shape, (100, 160, 3))
        self.assertEqual(image.dtype, np.uint8)
        self.assertTrue(np.any(np.all(image == PANEL, axis=2)))
        self.assertTrue(np.any(np.any(image != 0, axis=2)))

    def test_caption_focus_brightens_and_grows(self):
        shell = BoayoShell()
        points = shell.caption_polygons()["move"]
        shell.pointer_motion(*points.mean(axis=0))
        shell.tick(1.0)
        focused = shell.render().copy()
        shell.pointer_motion(320, 150)
        shell.tick(1.0)
        inactive = shell.render().copy()
        bright = np.all(focused > 200, axis=2).sum()
        self.assertGreater(bright, np.all(inactive > 200, axis=2).sum())

    def test_internal_move_resize_close(self):
        shell = BoayoShell()
        move = shell.caption_polygons()["move"].mean(axis=0)
        shell.pointer_motion(*move)
        shell.pointer_button(True)
        shell.pointer_motion(move[0] + 20, move[1] + 10)
        shell.pointer_button(False)
        self.assertAlmostEqual(shell.window.x, 87.84, places=1)
        self.assertAlmostEqual(shell.window.y, 38.08, places=1)

        right = shell.caption_polygons()["resize_right"].mean(axis=0)
        width = shell.window.width
        shell.pointer_motion(*right)
        shell.pointer_button(True)
        shell.pointer_motion(right[0] + 15, right[1])
        shell.pointer_button(False)
        self.assertGreater(shell.window.width, width)

        close = shell.caption_polygons()["close"].mean(axis=0)
        shell.pointer_motion(*close)
        shell.pointer_button(True)
        shell.pointer_button(False)
        self.assertFalse(shell.visible)

    def test_launcher_opens_builtin_when_command_is_missing(self):
        from boayo_shell import BoayoLauncherShell
        shell = BoayoLauncherShell(640, 360, ROOT / "boayo" / "apps.json")
        shell.selected_app = shell.apps[0]
        shell.hovered = "content"
        shell.pointer_button(True)
        shell.pointer_button(False)
        self.assertEqual(shell.active_app["id"], "dashboard")
        self.assertEqual(shell.render().shape, (360, 640, 3))

    def test_scene_is_complete_bosio_rgb(self):
        scene = BoayoScene(BoayoShell(320, 180), m=8)
        rgb = scene.render()
        self.assertEqual(rgb.shape, (20, 211, 64, 3))
        self.assertTrue(np.any(np.all(rgb > 230, axis=3)))

    def test_reconstructed_bosio_view(self):
        scene = BoayoScene(BoayoShell(320, 180), m=8).render()
        view = render_bosio_view(scene, m=8, width=160, height=90)
        self.assertEqual(view.shape, (90, 160, 3))
        self.assertLess(len(np.unique(view.reshape(-1, 3), axis=0)), 64)


if __name__ == "__main__":
    unittest.main()
