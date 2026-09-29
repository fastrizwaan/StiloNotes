# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

project(
  'stilonotes',
  version: '0.3',
  meson_version: '>= 0.62.0',
  license: 'GPL-3.0-or-later'
)

i18n = import('i18n')
python = import('python')
gnome = import('gnome')

project_id = 'io.github.fastrizwaan.StiloNotes'
project_name = 'Stilo Notes'

python_bin = python.find_installation('python3')
if not python_bin.found()
  error('No valid python3 binary found')
endif

python_dir = python_bin.get_install_dir()
pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), 'stilonotes')
localedir = join_paths(get_option('prefix'), get_option('localedir'))

application_id = project_id
if get_option('profile') == 'development'
  profile = 'Devel'
  application_id = '@0@.Devel'.format(application_id)
else
  profile = ''
endif

subdir('data')
subdir('stilonotes')
subdir('po')

gnome.post_install(
  gtk_update_icon_cache: true,
  glib_compile_schemas: true,
  update_desktop_database: true,
)
