"""Public Python SDK for BoAYo applications running on the BOSIO stack.

Applications draw only their content. This SDK owns the BOSIO IPC connection,
renders the BoAYo caption, and dispatches content input by window ID.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from bosio_wm_client import BosioWMClient
    from boayo_app_window import BoayoApplicationWindow, BoayoWindowState
    from boayo_ui import ACCENT, INK, MUTED, PANEL, WHITE, BoayoSurface
except ImportError:
    from .bosio_wm_client import BosioWMClient
    from .boayo_app_window import BoayoApplicationWindow, BoayoWindowState
    from .boayo_ui import ACCENT, INK, MUTED, PANEL, WHITE, BoayoSurface


SDK_VERSION = "0.2.0"


@dataclass(frozen=True)
class BoayoEvent:
    """Input in pixels relative to the application content rectangle."""

    window_id: int
    type: str
    x: float | None = None
    y: float | None = None
    pressed: bool | None = None
    button: str | None = None
    focused: bool | None = None
    state: BoayoWindowState | None = None


class BoayoSDK:
    """One BOSIO connection for any number of app-owned BoAYo windows.

    Use as ``with BoayoSDK('my-app') as sdk``. ``poll_events()`` must be called
    regularly even for static surfaces so caption buttons remain responsive.
    """

    def __init__(self, app_name, socket_path="/tmp/bosio-wm.sock", wm=None):
        self.app_name = str(app_name)
        self.socket_path = str(socket_path)
        self.wm = wm
        self.windows = {}
        self._reported_sizes = {}
        self._owns_connection = wm is None

    def __enter__(self):
        if self.wm is None:
            self.wm = BosioWMClient(self.app_name, socket_path=self.socket_path)
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.wm is not None and self._owns_connection:
            self.wm.close()
        self.wm = None
        self.windows.clear()
        self._reported_sizes.clear()

    def create_window(self, title, *, azimuth=None, elevation=None,
                      width_deg=38, height_deg=28, width=400, height=300,
                      accent=ACCENT):
        if self.wm is None:
            raise RuntimeError("enter the BoayoSDK context before creating windows")
        if azimuth is None:
            azimuth = float(os.environ.get("BOAYO_APP_AZIMUTH", "0"))
        if elevation is None:
            elevation = float(os.environ.get("BOAYO_APP_ELEVATION", "0"))
        window = BoayoApplicationWindow(
            self.wm, title, azimuth, elevation, width_deg, height_deg,
            width=width, height=height, accent=accent,
        )
        self.windows[window.window_id] = window
        self._reported_sizes[window.window_id] = (window.width_deg, window.height_deg)
        return window

    def window_state(self, window):
        """Read angular size, RGB pixel size, content pixel size and focus."""
        wid = window.window_id if isinstance(window, BoayoApplicationWindow) else int(window)
        owned = self.windows.get(wid)
        if owned is None:
            raise ValueError("window is not owned by this BoayoSDK instance")
        return owned.state

    def destroy_window(self, window):
        """Close one window while other windows of this app remain running."""
        wid = window.window_id if isinstance(window, BoayoApplicationWindow) else int(window)
        owned = self.windows.pop(wid, None)
        if owned is None:
            raise ValueError("window is not owned by this BoayoSDK instance")
        self.wm.destroy_window(wid)
        self._reported_sizes.pop(wid, None)
        owned.closed = True

    def poll_events(self):
        """Route one IPC event batch to all windows and return content events."""
        if self.wm is None:
            raise RuntimeError("BoayoSDK connection is closed")
        result = []
        for raw in self.wm.poll_events():
            window = self.windows.get(raw.get("window_id"))
            if window is None:
                continue
            kind = raw.get("type")
            area = None
            x = y = None
            if kind in ("pointer_motion", "pointer_button"):
                u, v = float(raw.get("u", -1)), float(raw.get("v", -1))
                area = window.frame.hit_test(u, v)
                if area == "content":
                    rect = window.frame.content
                    x = u * window.frame.width - rect.x
                    y = v * window.frame.height - rect.y
            window.handle_event(raw)
            if window.closed:
                self.windows.pop(window.window_id, None)
                self._reported_sizes.pop(window.window_id, None)
            if area == "content":
                result.append(BoayoEvent(window.window_id, kind, x, y,
                                         raw.get("pressed") if kind == "pointer_button" else None,
                                         raw.get("button") if kind == "pointer_button" else None))
            elif kind == "focus":
                result.append(BoayoEvent(window.window_id, kind,
                                         focused=window.focused, state=window.state))
        # BOSIO routes ordinary pointer events to the current hit window. A
        # dragged caption can move out from under the pointer, so follow the
        # pointer's world pose and button state until release regardless of hit.
        dragging = [window for window in self.windows.values() if window.drag is not None]
        if dragging:
            state = self.wm.get_state()
            pointer = state.get("pointer") or {}
            if "left" in pointer.get("buttons", ()):
                for window in dragging:
                    window.apply_gaze_drag(pointer["azimuth"], pointer["elevation"])
            else:
                for window in dragging:
                    window.cancel_drag()
        # One latest size snapshot per window per poll. Caption drags may be
        # followed from the global pointer after hit events stop arriving.
        for window in self.windows.values():
            size = (window.width_deg, window.height_deg)
            if size != self._reported_sizes.get(window.window_id):
                result.append(BoayoEvent(window.window_id, "resize", state=window.state))
                self._reported_sizes[window.window_id] = size
        return result


__all__ = ["BoayoSDK", "BoayoEvent", "BoayoWindowState", "BoayoApplicationWindow", "BoayoSurface",
           "ACCENT", "INK", "MUTED", "PANEL", "WHITE", "SDK_VERSION"]
