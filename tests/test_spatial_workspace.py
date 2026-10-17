"""Exercise app -> manager -> desktop -> owning app, including off-window drops."""
import sys
import base64
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "boayo"), str(ROOT / "vendor" / "bosio_SphericalWM" / "sw")]

from bosio_window_manager import SphericalWindowManager, WindowManagerError
from boayo_sdk import BoayoSDK
from boayo_spatial_workspace import SpatialWorkspace, storage_layout


class Client:
    def __init__(self, manager, owner):
        self.manager, self.owner = manager, owner
    def create_window(self, title, **kwargs):
        return self.manager.create_window(self.owner, title, **kwargs)
    def configure_window(self, wid, **kwargs):
        return self.manager.configure_window(self.owner, wid, **kwargs)
    def destroy_window(self, wid):
        return self.manager.destroy_window(self.owner, wid)
    def focus_window(self, wid, **kwargs):
        return self.manager.focus_window(wid, **kwargs)
    def update_surface(self, wid, rgb, x=0, y=0):
        height, width = rgb.shape[:2]
        return self.manager.update_surface(self.owner, wid, x, y, width, height, base64.b64encode(rgb.tobytes()).decode("ascii"))
    def poll_events(self):
        return self.manager.poll_events(self.owner)
    def get_state(self):
        return self.manager.state()
    def capture_pointer(self, wid):
        return self.manager.capture_pointer(self.owner, wid)
    def release_pointer(self):
        return self.manager.release_pointer(self.owner)
    def request_window_action(self, wid, action, **kwargs):
        return self.manager.request_window_action(self.owner, wid, action, **kwargs)


class SpatialIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.manager = SphericalWindowManager(m=8)
        self.client = Client(self.manager, "app")
        self.desktop = Client(self.manager, "desktop")
        self.sdk = BoayoSDK("app", wm=self.client)
        self.workspace = SpatialWorkspace(self.desktop)
        self.window = self.sdk.create_window("Studio", azimuth=179, elevation=4)
        self.window.present(lambda canvas, rect: canvas.rect(rect.x, rect.y, rect.width, rect.height, (32, 64, 96)))
        self.sdk.poll_events()

    def test_minimize_transition_preserves_cached_geometry_and_surface(self):
        w = self.manager.windows[self.window.window_id]
        before = (w.azimuth,w.elevation,w.width_deg,w.height_deg,w.surface_revision)
        self.window.minimize()
        self.window.tick(self.window._transition[0]+.1)
        self.assertEqual(before,(w.azimuth,w.elevation,w.width_deg,w.height_deg,w.surface_revision))
        self.assertTrue(w.mapped)

    def test_detached_gap_renders_and_selects_the_window_underneath(self):
        import numpy as np
        from bosio_window_manager import _shape_contains
        m = self.manager
        lower = m.create_window("lower", "Behind", azimuth=179, elevation=4,
            width_deg=38, height_deg=28, surface_width=400, surface_height=300)
        m.fill("lower", lower["window_id"], (224, 96, 64))
        m.raise_window("app", self.window.window_id)
        upper = m.windows[self.window.window_id]
        dot, x, y = m._project(upper, m._flat_rays)
        fx, fy = (x+1)*.5*399, (1-y)*.5*299
        gap = (dot>0) & (fx>32) & (fx<46) & (fy>70) & (fy<230)
        self.assertTrue(np.any(gap))
        front = m.render().reshape(-1,3).copy()
        m.configure_window("app", self.window.window_id, mapped=False)
        underneath = m.render().reshape(-1,3).copy()
        self.assertTrue(np.array_equal(front[gap], underneath[gap]))
        m.configure_window("app", self.window.window_id, mapped=True)
        az,el = self.window._gaze_at_surface(179,4,38,28,40/399,150/299)
        self.assertEqual(m.hit_test(az,el)[0].window_id, lower["window_id"])
        point = self.window.frame.controls()["move"].mean(axis=0)
        az,el = self.window._gaze_at_surface(179,4,38,28,float(point[0])/399,float(point[1])/299)
        self.assertEqual(m.hit_test(az,el)[0].window_id, self.window.window_id)

    def press_move(self):
        point = self.window.frame.controls()["move"].mean(axis=0)
        az, el = self.window._gaze_at_surface(self.window.azimuth, self.window.elevation,
            self.window.width_deg, self.window.height_deg,
            float(point[0]) / self.window.frame.width, float(point[1]) / self.window.frame.height)
        self.manager.pointer_warp(az, el)
        self.manager.pointer_button("left", True)
        self.sdk.poll_events()
        return az, el

    def minimize(self):
        self.window.minimize()
        started = self.window._transition[0]
        self.window.tick(started + .3)
        self.workspace.sync(self.manager.state())
        return self.workspace.cards[self.window.window_id]

    def card_gesture(self, az_delta=0, elevation=None):
        card = self.manager.windows[self.workspace.cards[self.window.window_id]]
        self.manager.pointer_warp(card.azimuth, card.elevation)
        self.manager.pointer_button("left", True)
        for event in self.desktop.poll_events():
            self.workspace.handle_event(event)
        self.manager.pointer_warp(card.azimuth + az_delta, card.elevation if elevation is None else elevation)
        self.manager.pointer_button("left", False)
        for event in self.desktop.poll_events():
            self.workspace.handle_event(event)
        return self.sdk.poll_events()

    def test_move_across_seam_drop_store_click_restores_normal_geometry(self):
        az, el = self.press_move()
        self.manager.pointer_warp(az + 5, -45)
        self.manager.pointer_button("left", False)
        events = self.sdk.poll_events()
        self.assertTrue(self.window._transition is not None or self.window.minimized)
        if self.window._transition is not None:
            self.window.tick(self.window._transition[0] + .3)
        self.assertFalse(self.manager.windows[self.window.window_id].mapped)
        self.assertNotEqual(self.manager.focused_window, self.window.window_id)
        self.workspace.sync(self.manager.state())
        self.card_gesture()
        self.assertTrue(self.manager.windows[self.window.window_id].mapped)
        self.assertEqual((self.window.azimuth, self.window.elevation), (179, 4))
        self.assertEqual((self.window.width_deg, self.window.height_deg), (38, 28))
        self.assertIsNone(self.manager._capture)

    def test_drag_card_previews_then_places_window_and_removes_card(self):
        self.minimize()
        card = self.manager.windows[self.workspace.cards[self.window.window_id]]
        self.manager.pointer_warp(card.azimuth, card.elevation)
        self.manager.pointer_button("left", True)
        for event in self.desktop.poll_events():
            self.workspace.handle_event(event)
        self.manager.pointer_warp(-165, -5)
        for event in self.desktop.poll_events():
            self.workspace.handle_event(event)
        preview = self.manager.windows[self.workspace._feedback["preview"]]
        self.assertTrue(preview.mapped)
        self.assertFalse(preview.input_enabled)
        self.assertEqual((preview.width_deg, preview.height_deg), (38, 28))
        self.manager.pointer_button("left", False)
        for event in self.desktop.poll_events():
            self.workspace.handle_event(event)
        self.sdk.poll_events()
        self.workspace.sync(self.manager.state())
        self.assertEqual((self.window.azimuth, self.window.elevation), (-165, -5))
        self.assertFalse(self.workspace.cards)

    def test_drag_card_down_closes_only_its_app_window(self):
        other = self.sdk.create_window("Other", azimuth=80)
        self.minimize()
        self.card_gesture(elevation=-80)
        self.assertTrue(self.window.closed)
        self.assertIn(other.window_id, self.manager.windows)
        self.workspace.sync(self.manager.state())
        self.assertFalse(self.workspace.cards)

    def test_cancel_below_storage_does_not_minimize_or_restore(self):
        self.press_move()
        self.manager.pointer_warp(170, -45)
        self.manager.cancel_pointer()
        self.sdk.poll_events()
        self.assertIsNone(self.window._transition)
        self.assertFalse(self.window.minimized)
        self.minimize()
        card = self.manager.windows[self.workspace.cards[self.window.window_id]]
        self.manager.pointer_warp(card.azimuth, card.elevation)
        self.manager.pointer_button("left", True)
        for event in self.desktop.poll_events():
            self.workspace.handle_event(event)
        self.manager.pointer_warp(170, -80)
        self.manager.cancel_pointer()
        for event in self.desktop.poll_events():
            self.workspace.handle_event(event)
        self.sdk.poll_events()
        self.assertTrue(self.window.minimized)
        self.assertFalse(self.window.closed)

    def test_neutral_card_drop_and_subthreshold_click(self):
        self.minimize()
        self.card_gesture(az_delta=4)
        self.assertTrue(self.window.minimized)
        self.card_gesture(az_delta=.3)
        self.assertFalse(self.window.minimized)

    def test_card_collision_across_180_and_dense_same_direction(self):
        windows = [dict(window_id=i, azimuth=179 if i % 2 else -179,
                        workspace={"dock_azimuth": 179 if i % 2 else -179}) for i in range(15)]
        layout = storage_layout(windows)
        for i, (az, el) in layout.items():
            self.assertGreater(el, -70)
            for j, (other_az, other_el) in layout.items():
                if i != j and el == other_el:
                    self.assertGreaterEqual(abs((az - other_az + 180) % 360 - 180), 18)

    def test_owner_actions_do_not_grant_cross_app_configuration(self):
        with self.assertRaises(WindowManagerError):
            self.desktop.configure_window(self.window.window_id, mapped=False)
        self.desktop.request_window_action(self.window.window_id, "minimize")
        self.assertTrue(self.manager.windows[self.window.window_id].mapped)
        self.sdk.poll_events()
        self.assertIsNotNone(self.window._transition)

    def test_feedback_does_not_take_input_or_focus_and_new_apps_stay_below_cards(self):
        card = self.minimize()
        other = self.sdk.create_window("Other", azimuth=179, elevation=-42)
        self.assertEqual(self.manager.hit_test(179, -42)[0].window_id, card)
        self.workspace._show_feedback("preview", 179, -42, 38, 28, "Studio", (96, 160, 192))
        self.assertEqual(self.manager.hit_test(179, -42)[0].window_id, card)
        self.assertEqual(self.manager.focused_window, other.window_id)


if __name__ == "__main__":
    unittest.main()
