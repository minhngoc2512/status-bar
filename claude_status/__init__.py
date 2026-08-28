"""Claude Status: Claude Code session, weather and crypto indicators for the top bar.

The GTK version is pinned here, before any submodule pulls in gi.repository --
importing Gtk without a version first would let PyGObject pick GTK 4.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

__version__ = "2.2.4"
