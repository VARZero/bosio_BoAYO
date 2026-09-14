#!/usr/bin/env python3
"""Small executable used by the BoAYO launcher integration example."""

from __future__ import annotations

import os
import time


def main():
    log_path = os.environ.get("BOAYO_EXAMPLE_LOG", "/tmp/boayo-example-app.log")
    with open(log_path, "a", encoding="utf-8") as stream:
        stream.write(f"dashboard started pid={os.getpid()}\n")
        stream.flush()
        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()
