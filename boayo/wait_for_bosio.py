#!/usr/bin/env python3
"""Wait until the BOSIO window-manager Unix socket accepts connections."""

import socket
import time


SOCKET_PATH = "/tmp/bosio-wm.sock"

for _ in range(180):
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.settimeout(1.0)
        connection.connect(SOCKET_PATH)
        break
    except OSError:
        time.sleep(1)
    finally:
        connection.close()
else:
    raise SystemExit("BOSIO window manager did not become ready within 180 seconds")
