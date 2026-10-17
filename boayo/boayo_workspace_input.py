"""Optional USB keyboard and gaze hover; no additional sensor hardware."""
from __future__ import annotations

import select


class WorkspaceInput:
    def __init__(self, wm):
        self.wm = wm
        self.last_pointer = None
        self.last_head = None
        self.gaze_mode = True
        self.keyboard = None
        try:
            from evdev import InputDevice, ecodes, list_devices
            self.codes = ecodes
            for path in list_devices():
                device = InputDevice(path)
                keys = device.capabilities().get(ecodes.EV_KEY, ())
                if ecodes.KEY_ENTER in keys and ecodes.KEY_TAB in keys:
                    self.keyboard = device
                    break
                device.close()
        except (ImportError, OSError):
            pass

    def tick(self, pointer, yaw, pitch, held=False):
        pose = (pointer.get("azimuth", 0), pointer.get("elevation", 0))
        head = (yaw, pitch)
        external_motion = self.last_pointer is not None and pose != self.last_pointer
        if external_motion and not held:
            self.gaze_mode = False
        if self.last_head is not None:
            daz = abs((yaw - self.last_head[0] + 180) % 360 - 180)
            if daz > .8 or abs(pitch - self.last_head[1]) > .8:
                self.gaze_mode = True
        if held:
            self.gaze_mode = True
        if self.gaze_mode and not pointer.get("buttons") and pose != head:
            self.wm.pointer_warp(yaw, pitch)
            pose = head
        self.last_pointer = pose
        if self.last_head is None or self.gaze_mode:
            self.last_head = head
        self._keyboard_tick()

    def _keyboard_tick(self):
        if self.keyboard is None:
            return
        try:
            if not select.select([self.keyboard.fd], [], [], 0)[0]:
                return
            mapping = {self.codes.KEY_TAB: "tab", self.codes.KEY_ENTER: "enter",
                       self.codes.KEY_SPACE: "space", self.codes.KEY_ESC: "escape",
                       self.codes.KEY_F6: "next"}
            for event in self.keyboard.read():
                if event.type == self.codes.EV_KEY and event.code in mapping and event.value != 2:
                    self.wm.input_key(mapping[event.code], event.value == 1)
        except OSError:
            self.keyboard.close()
            self.keyboard = None

    def close(self):
        if self.keyboard is not None:
            self.keyboard.close()
