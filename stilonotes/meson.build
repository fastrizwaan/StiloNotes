pkg_conf = configuration_data()
pkg_conf.set('APP_ID', application_id)
pkg_conf.set('VERSION', meson.project_version())
pkg_conf.set('PROFILE', profile)
pkg_conf.set('IS_DEVEL', profile == 'Devel' ? 'True' : 'False')
pkg_conf.set('PKGDATADIR', pkgdatadir)
pkg_conf.set('LOCALEDIR', localedir)
pkg_conf.set('PYTHON_DIR', python_dir)

configure_file(
  input: 'const.py.in',
  output: 'const.py',
  configuration: pkg_conf,
  install: true,
  install_dir: join_paths(python_dir, 'stilonotes')
)

configure_file(
  input: 'stilonotes.in',
  output: 'stilonotes',
  configuration: pkg_conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

sources = [
  '__init__.py',
  'application.py',
  'category_header_bar.py',
  'config_manager.py',
  'database.py',
  'editor.py',
  'editor_html.py',
  'exporter.py',
  'font_size_selector.py',
  'index.py',
  'main.py',
  'markdown_utils.py',
  'models.py',
  'notes_list.py',
  'selection_header_bar.py',
  'sidebar.py',
  'theme_selector.py',
  'window.py',
]

install_data(
  sources,
  install_dir: join_paths(python_dir, 'stilonotes')
)
