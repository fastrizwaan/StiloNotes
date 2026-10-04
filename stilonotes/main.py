# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from stilonotes.application import StiloApplication

def main(version: str = "0.7") -> int:
    app = StiloApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
