# Desktop file
desktop_conf = configuration_data()
desktop_conf.set('APP_ID', application_id)
desktop_file = configure_file(
  input: 'io.github.fastrizwaan.StiloNotes.desktop.in',
  output: '@0@.desktop'.format(application_id),
  configuration: desktop_conf,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

# AppStream Metainfo
metainfo_conf = configuration_data()
metainfo_conf.set('APP_ID', application_id)
metainfo_file = configure_file(
  input: 'io.github.fastrizwaan.StiloNotes.metainfo.xml.in',
  output: '@0@.metainfo.xml'.format(application_id),
  configuration: metainfo_conf,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'metainfo')
)

# GSettings Schema
install_data(
  'io.github.fastrizwaan.StiloNotes.gschema.xml',
  install_dir: join_paths(get_option('datadir'), 'glib-2.0', 'schemas')
)

# Icons
install_data(
  'icons/hicolor/scalable/apps/io.github.fastrizwaan.StiloNotes.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps')
)

install_data(
  'icons/hicolor/symbolic/apps/io.github.fastrizwaan.StiloNotes-symbolic.svg',
  'icons/hicolor/symbolic/apps/eraser3-symbolic.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'symbolic', 'apps')
)

# Assets (editor template, CSS)
install_subdir(
  '../assets',
  install_dir: pkgdatadir
)
