"""Send actual RGB changes; keep the acknowledged image across hide/show."""
import numpy as np


class SurfacePublisher:
    def __init__(self, wm, window_id):
        self.wm, self.window_id = wm, window_id
        self.previous = None
        self.sent_bytes = self.updates = self.skipped = 0
        self.last_rect = None
        self.last_bytes = 0

    def publish(self, image):
        image = np.ascontiguousarray(image, dtype=np.uint8)
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError('surface must have shape (height,width,3)')
        height, width = image.shape[:2]
        if self.previous is None or self.previous.shape != image.shape:
            x, y, w, h = 0, 0, width, height
        else:
            # Reduce contiguous byte rows first; only inspect columns in changed
            # rows. Avoid a tiny three-channel reduction for every screen pixel.
            changed = image.reshape(height,-1) != self.previous.reshape(height,-1)
            rows = np.flatnonzero(np.any(changed, axis=1))
            if not len(rows):
                self.skipped += 1
                self.last_rect, self.last_bytes = None, 0
                return False
            cols = np.flatnonzero(np.any(changed[rows[0]:rows[-1]+1], axis=0)) // 3
            x, y = int(cols[0]), int(rows[0])
            w, h = int(cols[-1]-x+1), int(rows[-1]-y+1)
        patch = image[y:y+h, x:x+w]
        # Keep the prior snapshot if IPC fails so the next call retries it.
        if self.previous is None or self.previous.shape != image.shape:
            self.wm.update_surface(self.window_id, patch)
        else:
            self.wm.update_surface(self.window_id, patch, x=x, y=y)
        self.previous = image.copy()
        self.last_rect, self.last_bytes = (x, y, w, h), patch.nbytes
        self.sent_bytes += patch.nbytes
        self.updates += 1
        return True
