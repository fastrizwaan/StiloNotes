#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import subprocess
import sys

destdir = os.environ.get('DESTDIR', '')

if not destdir:
    datadir = sys.argv[1]

    print('Compiling GSettings schemas…')
    subprocess.call(['glib-compile-schemas', os.path.join(datadir, 'glib-2.0', 'schemas')])

    print('Updating desktop database…')
    subprocess.call(['update-desktop-database', '-q', os.path.join(datadir, 'applications')])

    print('Updating icon cache…')
    subprocess.call(['gtk-update-icon-cache', '-qtf', os.path.join(datadir, 'icons', 'hicolor')])
