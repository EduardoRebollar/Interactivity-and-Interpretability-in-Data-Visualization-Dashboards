"""Vercel entry point.

Vercel's Python runtime looks for a WSGI callable named `app` in this module. Dash wraps Flask, so
the Flask server underneath is what gets served.

The import below also pulls the layout and data into module scope at cold start, which means a warm
container answers immediately.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The project is an application rather than an installed package, so put the repo root on the path
# before importing from `src`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app import server as app  # noqa: E402

__all__ = ["app"]
