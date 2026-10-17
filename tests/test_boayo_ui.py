import unittest
import sys
from unittest.mock import Mock, call, patch
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "boayo"), str(ROOT / "vendor" / "bosio_SphericalWM" / "sw")]

from boayo_ui import PANEL, BoayoSurface
from boayo_theme import CHROME, DANGER, TEXT
from boayo_shell import BoayoScene, BoayoShell, BoayoLauncherShell, BoayoWorkspace
from boayo_native_desktop import (BTN2AppDrag, click_launcher_at_gaze,
                                  launcher_contains_gaze, launcher_contains_point,
                                  launcher_point_at_gaze, open_dashboard)
from boayo_app_window import BoayoAppFrame, BoayoApplicationWindow
from boayo_sdk import BoayoSDK
from boayo_caption import button_image
from bosio_view_simulator import render_bosio_view


def mock_window_ids(wm, *app_ids, focused=True):
    apps = iter(app_ids)
    captions = iter(range(1000, 2000))
    def create(*args, **kwargs):
        wid = next(captions) if kwargs.get("workspace", {}).get("role") == "caption" else next(apps)
        return {"window_id": wid, "focused": focused}
    wm.create_window.side_effect = create


class BoayoUITests(unittest.TestCase):
    def test_launcher_outside_includes_black_margin_and_rest_of_sphere(self):
        shell = BoayoLauncherShell()
        self.assertTrue(launcher_contains_gaze(shell, 0, 0, 0, 0))
        self.assertFalse(launcher_contains_gaze(shell, 0, 0, 19, 0))
        self.assertIsNotNone(launcher_point_at_gaze(shell, 0, 0, 19, 0))
        self.assertFalse(launcher_contains_gaze(shell, 0, 0, 80, 0))
        self.assertFalse(launcher_contains_gaze(shell, 0, 0, 180, 0))
        rect = shell.window
        self.assertFalse(launcher_contains_point(shell, rect.x + 1, rect.y + 1))
        self.assertTrue(launcher_contains_point(shell, rect.x + 18, rect.y + 1))
        wm = Mock()
        with patch("boayo_shell.subprocess.Popen") as spawn:
            self.assertFalse(click_launcher_at_gaze(wm, shell, 3, 0, 0, 19, 0))
        spawn.assert_not_called()
        wm.configure_window.assert_not_called()

    def test_dashboard_button_launches_real_app_at_current_gaze(self):
        shell = BoayoLauncherShell(640, 360, ROOT / "boayo" / "apps.json")
        wm = Mock()
        wm.get_state.return_value = {"windows": []}
        with patch("boayo_shell.subprocess.Popen") as spawn:
            self.assertTrue(open_dashboard(wm, shell, 28, -12))
        self.assertEqual(shell.active_app["id"], "dashboard")
        self.assertEqual(spawn.call_args.kwargs["env"]["BOAYO_APP_AZIMUTH"], "28")
        self.assertEqual(spawn.call_args.kwargs["env"]["BOAYO_APP_ELEVATION"], "-12")

    def test_dashboard_button_restores_existing_app_without_duplicate_process(self):
        shell = BoayoLauncherShell()
        wm = Mock()
        wm.get_state.return_value = {"windows": [{"window_id": 7, "title": "Dashboard",
            "workspace": {"role": "app", "state": "minimized"}}]}
        with patch("boayo_shell.subprocess.Popen") as spawn:
            self.assertTrue(open_dashboard(wm, shell, -42, 10))
        spawn.assert_not_called()
        wm.request_window_action.assert_called_once_with(7, "restore", azimuth=-42, elevation=10)

    def test_btn2_app_drag_keeps_press_until_release(self):
        wm = Mock()
        drag = BTN2AppDrag(wm)
        drag.press(10, -30)
        drag.move(12, -31)
        self.assertTrue(drag.held)
        self.assertEqual(wm.pointer_button.call_args_list, [call(True)])
        drag.release(12, -31)
        self.assertFalse(drag.held)
        self.assertEqual(wm.pointer_warp.call_args_list,
                         [call(10, -30), call(12, -31)])
        self.assertEqual(wm.pointer_button.call_args_list,
                         [call(True), call(False)])

    def test_sdk_drag_continues_after_pointer_leaves_window(self):
        wm = Mock()
        mock_window_ids(wm, 25)
        with BoayoSDK("drag-app", wm=wm) as sdk:
            window = sdk.create_window("Drag", azimuth=10, elevation=-30)
            point = window.frame.controls()["move"].mean(axis=0)
            u, v = float(point[0]) / window.frame.width, float(point[1]) / window.frame.height
            start_az, start_el = window._gaze_at_surface(10, -30, 38, 28, u, v)
            wm.poll_events.side_effect = [
                [{"type": "pointer_button", "window_id": 25, "button": "left",
                  "pressed": True, "u": u, "v": v}], [], [],
            ]
            wm.get_state.side_effect = [
                {"pointer": {"azimuth": start_az, "elevation": start_el, "buttons": ["left"]}},
                {"pointer": {"azimuth": start_az + 3, "elevation": start_el + 1,
                             "buttons": ["left"]}},
                {"pointer": {"azimuth": start_az + 3, "elevation": start_el + 1,
                             "buttons": []}},
            ]
            sdk.poll_events()
            sdk.poll_events()  # No hit event: the caption moved away from gaze.
            self.assertAlmostEqual(window.azimuth, 13)
            self.assertAlmostEqual(window.elevation, -29)
            sdk.poll_events()  # Release also missed the window.
            self.assertIsNone(window.drag)

    def test_sdk_reports_window_size_and_focus_without_resizing_rgb_surface(self):
        wm = Mock()
        mock_window_ids(wm, 26)
        wm.get_state.return_value = {"pointer": {"buttons": []}}
        with BoayoSDK("state-app", wm=wm) as sdk:
            window = sdk.create_window("State", width_deg=38, height_deg=28,
                                       width=400, height=300)
            initial = sdk.window_state(window.window_id)
            self.assertTrue(initial.focused)
            self.assertEqual((initial.surface_width, initial.surface_height), (400, 300))
            self.assertEqual((initial.content_width, initial.content_height),
                             (window.frame.content.width, window.frame.content.height))
            point = window.frame.controls()["resize_right"].mean(axis=0)
            u, v = float(point[0]) / 400, float(point[1]) / 300
            wm.poll_events.side_effect = [[
                {"type": "focus", "window_id": 26, "focused": True},
                {"type": "pointer_button", "window_id": 26, "button": "left",
                 "pressed": True, "u": u, "v": v},
                {"type": "pointer_motion", "window_id": 26, "u": u + .1, "v": v},
            ], []]
            events = sdk.poll_events()
            self.assertEqual([event.type for event in events], ["focus", "resize"])
            self.assertTrue(events[0].focused)
            self.assertTrue(window.focused)
            self.assertAlmostEqual(events[1].state.width_deg, 41.8)
            self.assertEqual((events[1].state.surface_width, events[1].state.surface_height),
                             (400, 300))
            self.assertEqual(sdk.window_state(window).width_deg, events[1].state.width_deg)
            self.assertEqual(sdk.poll_events(), [])  # No duplicate resize event.

    def test_sdk_emits_resize_when_caption_drag_leaves_window(self):
        wm = Mock()
        mock_window_ids(wm, 27)
        with BoayoSDK("off-window-resize", wm=wm) as sdk:
            window = sdk.create_window("Resize", azimuth=10, elevation=-30)
            point = window.frame.controls()["resize_right"].mean(axis=0)
            u, v = float(point[0]) / window.frame.width, float(point[1]) / window.frame.height
            start_az, start_el = window._gaze_at_surface(10, -30, 38, 28, u, v)
            wm.poll_events.side_effect = [
                [{"type": "pointer_button", "window_id": 27, "button": "left",
                  "pressed": True, "u": u, "v": v}], [], [],
            ]
            wm.get_state.side_effect = [
                {"pointer": {"azimuth": start_az, "elevation": start_el, "buttons": ["left"]}},
                {"pointer": {"azimuth": start_az + 3, "elevation": start_el, "buttons": ["left"]}},
                {"pointer": {"azimuth": start_az + 3, "elevation": start_el, "buttons": []}},
            ]
            self.assertEqual(sdk.poll_events(), [])
            changed = sdk.poll_events()
            self.assertEqual(len(changed), 1)
            self.assertEqual(changed[0].type, "resize")
            self.assertGreater(changed[0].state.width_deg, 38)
            self.assertEqual(sdk.poll_events(), [])
            self.assertIsNone(window.drag)

    def test_caption_gray_is_neutral_for_rgb332_palette(self):
        frame = BoayoAppFrame(400, 300, "Color")
        frame.focused = True
        image = frame.render(lambda *_: None)
        point = frame.controls()["move"].mean(axis=0).astype(int)
        self.assertEqual(tuple(image[point[1], point[0]]), (64, 64, 64))
        red, green, blue = map(int, image[point[1], point[0]])
        index = (red & 224) | ((green >> 3) & 28) | (blue >> 6)
        level = index >> 5
        self.assertEqual((index >> 2) & 7, level)
        self.assertEqual(index & 3, (level * 255 // 7) >> 6)

    def test_sdk_routes_content_events_between_multiple_windows(self):
        wm = Mock()
        mock_window_ids(wm, 11, 12)
        with BoayoSDK("two-windows", wm=wm) as sdk:
            first = sdk.create_window("First", azimuth=0, elevation=0)
            second = sdk.create_window("Second", azimuth=20, elevation=0)
            rect = first.frame.content
            content_u = (rect.x + 20) / first.frame.width
            content_v = (rect.y + 30) / first.frame.height
            wm.poll_events.return_value = [
                {"type": "pointer_button", "window_id": 11, "button": "left", "pressed": True,
                 "u": content_u, "v": content_v},
                {"type": "window_action", "window_id": 12, "action": "close"},
            ]
            events = sdk.poll_events()
            self.assertEqual(len(events), 1)
            self.assertEqual((events[0].window_id, events[0].type), (11, "pointer_button"))
            self.assertAlmostEqual(events[0].x, 20)
            self.assertAlmostEqual(events[0].y, 30)
            self.assertTrue(second.closed)
            self.assertFalse(first.closed)
            self.assertEqual(list(sdk.windows), [11])
            wm.destroy_window.assert_called_once_with(12)

    def test_sdk_can_present_rendered_rgb_inside_boayo_caption(self):
        wm = Mock()
        mock_window_ids(wm, 21)
        with BoayoSDK("image-app", wm=wm) as sdk:
            window = sdk.create_window("Image", azimuth=0, elevation=0)
            window.present_rgb(np.full((40, 80, 3), (20, 190, 70), dtype=np.uint8))
            image = next(c.args[1] for c in wm.update_surface.call_args_list if c.args[0] == window.window_id)
            self.assertTrue(np.any(np.all(image == (20, 190, 70), axis=2)))
            self.assertTrue(np.any(np.all(image[window.frame.caption.y + 10] == (64, 96, 128), axis=1)))

    def test_application_caption_stays_within_its_surface_and_panel_has_none(self):
        for width in (260, 400, 640):
            frame = BoayoAppFrame(width, 220, "Demo")
            for polygon in frame.controls().values():
                self.assertGreaterEqual(polygon[:, 0].min(), frame.caption.x)
                self.assertLessEqual(polygon[:, 0].max(), frame.caption.x + frame.caption.width)
            image = frame.render(lambda canvas, rect: canvas.rect(rect.x + 20, rect.y + 20, 25, 20, (52, 124, 255)))
            self.assertTrue(np.all(image[frame.content.y + 25, frame.content.x + 25] == (52, 124, 255)))
            self.assertTrue(np.any(np.all(image[frame.caption.y + 10] == (64, 96, 128), axis=1)))
        self.assertEqual(BoayoLauncherShell().caption_polygons(), {})

    def test_application_handles_are_detached_and_close_is_visible(self):
        frame = BoayoAppFrame(400, 300, "Demo")
        self.assertEqual(set(frame.controls()), {"move", "resize_right", "close"})
        move = frame.controls()["move"]
        self.assertLess(move[:, 0].max(), frame.shell.x)
        self.assertGreater(frame.controls()["resize_right"][:, 0].min(), frame.shell.x + frame.shell.width)
        image = frame.render(lambda *_: None)
        gap = image[frame.height // 2, 31:frame.shell.x]
        self.assertTrue(np.all(gap == (3, 5, 8)))
        self.assertIsNone(frame.hit_test(40 / frame.width, .5))

    def test_close_button_is_large_visible_and_outside_app_content(self):
        for width, height in ((240, 170), (400, 300), (640, 440)):
            frame = BoayoAppFrame(width, height, "A long application title")
            frame.focused = True
            poly = frame.controls()["close"]
            x, y = poly.min(axis=0).astype(int)
            w, h = (poly.max(axis=0) - poly.min(axis=0)).astype(int)
            self.assertGreaterEqual(min(w, h), 40)
            self.assertGreater(x, frame.shell.x + frame.shell.width)
            self.assertEqual(frame.hit_test((x+w/2)/width, (y+h/2)/height), "close")
            image = frame.render(lambda canvas, rect: canvas.clear((0, 0, 0)))
            button = image[y:y+h, x:x+w]
            self.assertTrue(np.any(np.all(button == DANGER, axis=2)))
            self.assertTrue(np.any(np.all(button == TEXT, axis=2)))

    def test_close_requires_matching_press_release_and_respects_cancellation(self):
        wm = Mock()
        mock_window_ids(wm, 9)
        app = BoayoApplicationWindow(wm, "Demo", 10, 5, 38, 28)
        point = app.frame.controls()["close"].mean(axis=0)
        event = dict(type="pointer_button", window_id=9, button="left",
                     u=float(point[0])/app.frame.width, v=float(point[1])/app.frame.height)
        app.handle_event(dict(event, pressed=False))
        wm.destroy_window.assert_not_called()
        for cancellation in (
            dict(event, pressed=False, u=.5, v=.5),
            dict(type="pointer_cancel", window_id=9),
            dict(type="pointer_leave", window_id=9),
            dict(type="key", window_id=9, key="escape", pressed=True),
        ):
            app.handle_event(dict(event, pressed=True))
            wm.destroy_window.assert_not_called()
            app.handle_event(cancellation)
            app.handle_event(dict(event, pressed=False))
            self.assertFalse(app.closed)
        app.handle_event(dict(event, pressed=True))
        app.handle_event(dict(event, pressed=False))
        self.assertTrue(app.closed)
        app.handle_event(dict(event, pressed=False))
        self.assertEqual(wm.destroy_window.call_args_list.count(call(9)), 1)

    def test_application_caption_move_and_resize_configure_bosio_window(self):
        wm = Mock()
        mock_window_ids(wm, 9)
        app = BoayoApplicationWindow(wm, "Demo", 10, 5, 38, 28)
        point = app.frame.controls()["move"].mean(axis=0)
        u, v = float(point[0]) / app.frame.width, float(point[1]) / app.frame.height
        app.handle_event({"type": "pointer_button", "window_id": 9, "button": "left", "pressed": True, "u": u, "v": v})
        app.handle_event({"type": "pointer_motion", "window_id": 9, "u": u + .1, "v": v})
        wm.configure_window.assert_called_with(9, azimuth=13.8, elevation=5.0)
        app.handle_event({"type": "pointer_button", "window_id": 9, "button": "left", "pressed": False, "u": u + .1, "v": v})
        wm.configure_window.reset_mock()
        point = app.frame.controls()["resize_right"].mean(axis=0)
        u, v = float(point[0]) / app.frame.width, float(point[1]) / app.frame.height
        app.handle_event({"type": "pointer_button", "window_id": 9, "button": "left", "pressed": True, "u": u, "v": v})
        app.handle_event({"type": "pointer_motion", "window_id": 9, "u": u + .1, "v": v})
        self.assertAlmostEqual(wm.configure_window.call_args.kwargs["width_deg"], 41.8)
        self.assertEqual(wm.configure_window.call_args.kwargs["height_deg"], 28.0)

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
        shell.pointer_motion(shell.window.x + shell.window.width * .5, shell.window.y + 35)
        with patch("boayo_shell.subprocess.Popen") as spawn:
            shell.pointer_button(True)
            shell.pointer_button(False)
        spawn.assert_called_once()
        self.assertIn(str(ROOT / "boayo"), spawn.call_args.kwargs["env"]["PYTHONPATH"])
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
        shell.pointer_motion(100, 150)
        self.assertEqual(shell.render_key(), first_key)
        self.assertTrue(np.array_equal(shell.render(), first))
        shell.pointer_motion(320, 80)
        self.assertIs(shell.hovered_app, shell.apps[0])
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
