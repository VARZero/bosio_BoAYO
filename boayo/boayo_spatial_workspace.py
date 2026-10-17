"""World-anchored storage cards and drag feedback for BoAYo applications.

Only RGB windows and existing spherical geometry are used. No output-core or
bitstream changes, browser runtime, alpha channel, or result notifications.
"""
from __future__ import annotations

import math
import numpy as np

from boayo_ui import BLACK, BoayoSurface
from boayo_surface_updates import SurfacePublisher
from boayo_theme import CHROME, RAISED, EDGE, FOCUS, TEXT, SUBTLE, DANGER


def angular_distance(a, b):
    return abs((float(a) - float(b) + 180) % 360 - 180)


def storage_layout(windows, elevation=-42, width=16, height=5):
    """Assign nonoverlapping rows, including cards across the +/-180 seam."""
    placed = []
    result = {}
    for window in sorted(windows, key=lambda item: item["window_id"]):
        az = window["workspace"].get("dock_azimuth", window["azimuth"])
        # A tangent panel spans more longitude at lower elevations. Account
        # for its bottom corners rather than comparing raw width_deg to yaw.
        for offset in range(360):
            candidate = (az + offset * 2 + 180) % 360 - 180
            for row in range(5):
                el = elevation - row * (height + 1)
                denominator = math.cos(math.radians(el)) - math.tan(math.radians(height / 2)) * abs(math.sin(math.radians(el)))
                span = math.degrees(math.atan(math.tan(math.radians(width / 2)) / max(.01, denominator)))
                if not any(p[1] == row and angular_distance(p[0], candidate) < span + p[2] + 2 for p in placed):
                    break
            else:
                continue
            break
        else:
            raise ValueError("storage ring is full")
        placed.append((candidate, row, span))
        result[window["window_id"]] = (candidate, el)
    return result


class SpatialWorkspace:
    """Desktop-owned cards issue actions to each application's owning SDK."""
    def __init__(self, wm, storage_elevation=-42, close_elevation=-76):
        self.wm = wm
        self.storage_elevation = float(storage_elevation)
        self.close_elevation = float(close_elevation)
        self.cards = {}
        self.targets = {}
        self.drag = None
        self.hovered = None
        self._feedback = {}
        self._feedback_keys = {}
        self._card_keys = {}
        self._publishers = {}
        self._cancel_serial = 0

    def _create(self, title, azimuth, elevation, width, height, role, input_enabled=False, surface_height=96):
        info = self.wm.create_window(title, azimuth=azimuth, elevation=elevation,
            width_deg=width, height_deg=height, surface_width=320, surface_height=surface_height,
            always_on_top=True, decorated=False, input_enabled=input_enabled,
            focus_on_create=False, workspace={"role": role})
        return info["window_id"]

    def _publish_surface(self, wid, image):
        publisher = self._publishers.setdefault(wid, SurfacePublisher(self.wm, wid))
        publisher.publish(image)

    def _card_image(self, target, selected=False, dim=False, closing=False):
        canvas = BoayoSurface(320, 96)
        border = DANGER if closing else (FOCUS if selected else EDGE)
        color = RAISED if selected else CHROME
        if dim:
            color = tuple(c // 2 for c in color)
            border = tuple(c // 2 for c in border)
        canvas.rounded_rect(2, 2, 316, 92, 18, border)
        canvas.rounded_rect(5, 5, 310, 86, 15, color)
        for x in (16, 24):
            for y in (31, 43, 55):
                canvas.circle(x, y, 2, SUBTLE)
        canvas.text(target["title"][:12], 42, 20, TEXT, scale=3, bold=True)
        canvas.text("UP: OPEN  DOWN: CLOSE" if selected else "STORED / LOOK TO OPEN",
                    42, 61, FOCUS if selected else SUBTLE, scale=1)
        return canvas.image()

    def _show_feedback(self, name, az, el, width, height, label, color):
        key = (round(az, 2), round(el, 2), round(width, 2), round(height, 2), label, color)
        if name not in self._feedback:
            self._feedback[name] = self._create(label, az, el, width, height, "feedback",
                                               surface_height=240 if name == "preview" else 96)
        if self._feedback_keys.get(name) == key:
            return
        wid = self._feedback[name]
        self.wm.configure_window(wid, azimuth=az, elevation=el, width_deg=width,
                                 height_deg=height, mapped=True)
        canvas = BoayoSurface(320, 240 if name == "preview" else 96)
        canvas.rounded_rect(0, 0, canvas.width, canvas.height, 12, color)
        canvas.rounded_rect(4, 4, canvas.width - 8, canvas.height - 8, 9, CHROME)
        if name == "preview":
            canvas.rect(4, 58, canvas.width - 8, 2, color)
            canvas.text("RELEASE TO PLACE", 22, 108, TEXT, scale=2)
            canvas.text("ESC / BTN3: CANCEL", 22, 180, SUBTLE, scale=1)
        canvas.text(label[:13], 13, 16 if name == "preview" else 30, color, scale=3, bold=True)
        self._publish_surface(wid, canvas.image())
        self._feedback_keys[name] = key

    def _hide_feedback(self, keep=()):
        for name, wid in self._feedback.items():
            if name not in keep and self._feedback_keys.get(name) is not None:
                self.wm.configure_window(wid, mapped=False)
                self._feedback_keys[name] = None

    def sync(self, state):
        apps = [w for w in state.get("windows", ()) if w.get("workspace", {}).get("role") == "app"]
        self.targets = {w["window_id"]: w for w in apps}
        minimized = [w for w in apps if w["workspace"].get("state") == "minimized"]
        layout = storage_layout(minimized, self.storage_elevation)
        for target_id in list(self.cards):
            if target_id not in layout:
                if self.drag and self.drag["target"] == target_id:
                    self.cancel()
                wid = self.cards.pop(target_id)
                self.wm.destroy_window(wid)
                self._publishers.pop(wid, None)
                self._card_keys.pop(target_id, None)
        pointer = state.get("pointer") or {}
        hovered = next((target for target, card in self.cards.items()
                        if card == pointer.get("window_id")), None)
        self.hovered = hovered
        for target in minimized:
            target_id = target["window_id"]
            az, el = layout[target_id]
            if target_id not in self.cards:
                self.cards[target_id] = self._create(target["title"], az, el, 16, 5, "storage", True)
            dim = bool(self.drag and self.drag["target"] == target_id and self.drag["moved"])
            closing = bool(dim and pointer.get("elevation", 0) <= self.close_elevation)
            selected = hovered == target_id or state.get("focused_window") == self.cards[target_id]
            key = (az, el, target["title"], selected, dim, closing)
            if self._card_keys.get(target_id) != key:
                self.wm.configure_window(self.cards[target_id], azimuth=az, elevation=el)
                self._publish_surface(self.cards[target_id], self._card_image(target, selected, dim, closing))
                self._card_keys[target_id] = key
        if self.drag:
            if pointer.get("cancel_serial", 0) != self._cancel_serial:
                self.cancel()
            elif "left" in pointer.get("buttons", ()):
                self.move(pointer["azimuth"], pointer["elevation"])
            else:
                final = pointer.get("last_left_release") or pointer
                self.finish(final.get("azimuth", self.drag["az"]), final.get("elevation", self.drag["el"]))
        self._cancel_serial = pointer.get("cancel_serial", 0)
        if not self.drag:
            moving = next((w for w in apps if w["workspace"].get("state") == "moving"), None)
            if moving:
                az = pointer.get("azimuth", moving["azimuth"])
                self._show_feedback("store", az, -36, 30, 5, "RELEASE TO STORE", FOCUS)
                self._hide_feedback(("store",))
            else:
                self._hide_feedback()

    def handle_event(self, event):
        target = next((target for target, card in self.cards.items() if card == event.get("window_id")), None)
        if target is None:
            return False
        kind = event.get("type")
        if kind == "pointer_cancel":
            self.cancel()
        elif kind == "pointer_button" and event.get("button") == "left":
            az, el = event.get("azimuth"), event.get("elevation")
            if az is None or el is None:
                return True
            if event.get("pressed"):
                self.drag = {"target": target, "az": az, "el": el, "moved": False,
                             "cancel_serial": self._cancel_serial}
                self.wm.capture_pointer(self.cards[target])
            elif self.drag:
                self.finish(az, el)
        elif kind == "pointer_motion" and self.drag:
            self.move(event["azimuth"], event["elevation"])
        elif kind == "key" and event.get("pressed"):
            if event.get("key") in ("enter", "space"):
                self.wm.request_window_action(target, "restore")
            elif event.get("key") == "escape":
                self.cancel()
        return True

    def move(self, az, el):
        if not self.drag:
            return
        drag = self.drag
        distance = math.hypot(angular_distance(az, drag["az"]) * math.cos(math.radians(drag["el"])), el - drag["el"])
        drag["moved"] |= distance > 1.0
        if not drag["moved"]:
            return
        target = self.targets.get(drag["target"])
        if target is None:
            self.cancel()
            return
        self._show_feedback("ghost", az, el, 14, 4, target["title"], FOCUS)
        keep = ["ghost"]
        if el > drag["el"] + 5:
            geometry = target["workspace"].get("restore", target)
            self._show_feedback("preview", az, max(-30, el), geometry["width_deg"],
                                geometry["height_deg"], target["title"], FOCUS)
            keep.append("preview")
        if el <= self.close_elevation:
            self._show_feedback("close", az, self.close_elevation, 28, 5, "RELEASE TO CLOSE", DANGER)
            keep.append("close")
        self._hide_feedback(keep)

    def finish(self, az, el):
        if not self.drag:
            return
        self.move(az, el)
        if not self.drag:
            return
        drag = self.drag
        if not drag["moved"]:
            self.wm.request_window_action(drag["target"], "restore")
        elif el <= self.close_elevation:
            self.wm.request_window_action(drag["target"], "close")
        elif el > drag["el"] + 5:
            self.wm.request_window_action(drag["target"], "restore", azimuth=az, elevation=max(-30, el))
        self.cancel()

    def cancel(self):
        was_dragging = self.drag is not None
        self.drag = None
        if was_dragging:
            self.wm.release_pointer()
        self._hide_feedback()

    def close(self):
        self.cancel()
        for wid in list(self.cards.values()) + list(self._feedback.values()):
            self.wm.destroy_window(wid)
        self.cards.clear()
        self._feedback.clear()
