# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys

# Enable portal usage so WebKit uses XDG Desktop Portal Print dialog with print preview
os.environ.setdefault("WEBKIT_USE_PORTAL", "1")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from stilonotes.application import StiloApplication

def main(version: str = "1.1") -> int:
    app = StiloApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
