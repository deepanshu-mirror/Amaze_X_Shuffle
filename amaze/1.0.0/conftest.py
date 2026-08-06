"""Pytest bootstrap.

Adds the app's ``src/`` directory to ``sys.path`` so tests can import the
flat-module layout exactly as it runs inside the Shuffle container (where
``COPY src /app`` makes ``app.py`` and ``amaze_client.py`` siblings).
"""

import os
import sys

SRC = os.path.join(os.path.dirname(__file__), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
