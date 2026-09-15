import unittest
import sys
from unittest.mock import Mock, patch
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "boayo"), str(ROOT / "vendor" / "bosio_SphericalWM" / "sw")]

from boayo_ui import PANEL, BoayoSurface
from boayo_shell import BoayoScene, BoayoShell, BoayoLauncherShell, BoayoWorkspace
from boayo_native_desktop import click_launcher_at_gaze
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

    def test_rounded_panel_corners_blend_into_the_existing_surface(self):
        surface = BoayoSurface(80, 60, background=(0, 0, 0))
        surface.rounded_rect(10, 10, 50, 38, 16, (255, 255, 255))
        image = surface.image()
        corner = image[10:26, 10:26, 0]
        self.assertTrue(np.any((corner > 0) & (corner < 255)))
        self.assertTrue(np.all(image[30, 20] == 255))
        self.assertTrue(np.all(image[10, 10] == 0))

    def test_circle_and_polygon_edges_have_partial_coverage(self):
        surface = BoayoSurface(80, 60, background=(0, 0, 0))
        surface.circle(20, 20, 8, (255, 255, 255))
        self.assertTrue(np.any((surface.image()[10:30, 10:30, 0] > 0) &
                               (surface.image()[10:30, 10:30, 0] < 255)))
        surface.polygon(((41.3, 10), (70, 11.5), (53, 40)), (255, 255, 255))
        self.assertTrue(np.any((surface.image()[8:42, 38:72, 0] > 0) &
                               (surface.image()[8:42, 38:72, 0] < 255)))

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

    def test_launcher_launches_external_app_without_placeholder_surface(self):
        shell = BoayoLauncherShell(640, 360, ROOT / "boayo" / "apps.json")
        shell.selected_app = shell.apps[0]
        shell.hovered = "content"
        with patch("boayo_shell.subprocess.Popen") as spawn:
            shell.pointer_button(True)
            shell.pointer_button(False)
        spawn.assert_called_once()
        self.assertEqual(shell.active_app["id"], "dashboard")
        self.assertTrue(np.all(shell.render() == (3, 5, 8)))

    def test_failed_launch_keeps_launcher_visible(self):
        shell = BoayoLauncherShell(640, 360, ROOT / "boayo" / "apps.json")
        shell.selected_app = shell.apps[0]
        with patch("boayo_shell.subprocess.Popen", side_effect=OSError("not executable")):
            self.assertFalse(shell.launch_app(shell.selected_app))
        self.assertIsNone(shell.active_app)
        self.assertTrue(np.any(np.all(shell.render() == (250, 250, 249), axis=2)))

    def test_successful_gaze_launch_unmaps_only_the_launcher(self):
        shell = BoayoLauncherShell(640, 360, ROOT / "boayo" / "apps.json")
        wm = Mock()
        with patch("boayo_shell.subprocess.Popen"):
            self.assertTrue(click_launcher_at_gaze(wm, shell, 3, 0, 0, 0, 8))
        self.assertEqual(shell.active_app["id"], "dashboard")
        wm.configure_window.assert_called_once_with(3, mapped=False)

    def test_scene_is_complete_bosio_rgb(self):
        scene = BoayoScene(BoayoShell(320, 180), m=8)
        rgb = scene.render()
        self.assertEqual(rgb.shape, (20, 211, 64, 3))
        self.assertTrue(np.any(np.all(rgb > 230, axis=3)))

    def test_workspace_adds_gaze_panel_and_keeps_previous_visible(self):
        workspace = BoayoWorkspace(m=8, base_azimuth=0, base_elevation=0, count=1, launcher=True,
                                   apps_path=ROOT / "boayo" / "apps.json")
        self.assertEqual(len(workspace.items), 1)
        panel = workspace.add_panel(20, 5, {"id": "demo", "name": "Demo", "color": "#347CFF"})
        self.assertFalse(panel.auto_hide)
        self.assertEqual(len(workspace.items), 1)
        self.assertIs(workspace.items[-1][0], panel)
        self.assertIs(panel.active_app, workspace.items[-1][0].active_app)
        workspace.gaze(20, 5)
        self.assertTrue(panel.visible)
        workspace.gaze(170, -60)
        self.assertTrue(panel.visible)

    def test_new_launcher_replaces_only_the_old_launcher(self):
        workspace = BoayoWorkspace(m=8, base_azimuth=0, base_elevation=0, count=1, launcher=True,
                                   apps_path=ROOT / "boayo" / "apps.json")
        app_window = workspace.add_panel(10, 0, {"id": "demo", "name": "Demo", "color": "#347CFF"})
        app_window.active_app = {"id": "demo", "name": "Demo", "color": "#347CFF"}
        launcher = workspace.add_panel(20, 0)
        self.assertEqual(len(workspace.items), 2)
        self.assertIs(workspace.items[-1][0], launcher)
        self.assertIs(workspace.items[0][0], app_window)
        self.assertIsNotNone(app_window.active_app)
        self.assertIsNone(launcher.active_app)

    def test_launcher_scroll_changes_selected_row(self):
        shell = BoayoLauncherShell(640, 360, ROOT / "boayo" / "apps.json")
        self.assertFalse(shell.scroll(1))
        self.assertEqual(shell.scroll_offset, 0)
        self.assertTrue(shell.scroll(-1))
        self.assertEqual(shell.scroll_offset, 1)

    def test_launcher_surface_key_changes_only_when_visible_content_changes(self):
        shell = BoayoLauncherShell(640, 360, ROOT / "boayo" / "apps.json")
        first_key = shell.render_key()
        first = shell.render().copy()
        shell.pointer_motion(320, 150)
        self.assertEqual(shell.render_key(), first_key)
        self.assertTrue(np.array_equal(shell.render(), first))
        shell.selected_app = shell.apps[0]
        self.assertNotEqual(shell.render_key(), first_key)
        self.assertFalse(np.array_equal(shell.render(), first))

    def test_mouse_cursor_is_rendered_on_panel(self):
        shell = BoayoShell(320, 180)
        shell.mouse_motion(160, 90)
        image = shell.render()
        self.assertTrue(np.any(np.all(image[84:97, 154:173] == (250, 250, 249), axis=2)))

    def test_reconstructed_bosio_view(self):
        scene = BoayoScene(BoayoShell(320, 180), m=8).render()
        view = render_bosio_view(scene, m=8, width=160, height=90)
        self.assertEqual(view.shape, (90, 160, 3))
        self.assertLess(len(np.unique(view.reshape(-1, 3), axis=0)), 64)


if __name__ == "__main__":
    unittest.main()
