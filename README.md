# Stilo Notes 🖊️

<p align="center">
  <img src="assets/icons/io.github.fastrizwaan.StiloNotes.svg" width="128" height="128" alt="Stilo Notes Icon">
</p>

<p align="center">
  <b>Elegant, distraction-free note taking for GNOME & Libadwaita.</b><br>
  Combines the clean, thoughtful architecture and UI of <a href="https://gitlab.gnome.org/World/iotas">Iotas</a> with the dynamic WebKit live Markdown-to-HTML rendering engine of <a href="https://github.com/fastrizwaan/TeddyNotes">TeddyNotes</a>.
</p>

---

## ✨ Features

- **Dynamic WebKit Markdown Live Rendering**: Type standard markdown syntax (`# `, `## `, `### `, `- [ ]`, `*`, `**`, `>`, ````lang````, `| a | b |`, `---`) and watch it dynamically transform into rich, beautifully styled interactive HTML on the fly.
- **Interactive Checklists**: Click checkboxes (`- [ ]` and `- [x]`) directly in the editor to toggle tasks and mark them completed.
- **Iotas-Inspired Clean UI**:
  - Distraction-free two-page navigation (`Adw.NavigationView`): Index and Editor.
  - Collapsible folder and category sidebar (`Adw.OverlaySplitView`).
  - Fast search with instant filtering across note titles, contents, and #tags.
  - Multi-selection mode for batch operations.
- **Session Memory**: Remembers window geometry, last active folder/category, and previously viewed note.
- **Real-Time Note Statistics**: Instant word count, character count, paragraph count, and reading time estimate.
- **Seamless Theme Sync**: Automatic synchronization with Libadwaita dark and light modes, with a manual quick-toggle.
- **Multiple Export Formats**: Export notes cleanly to Markdown (`.md`), HTML (`.html`), or Plain Text (`.txt`).
- **Cute Design & Mascot**: Includes custom Adwaita squircle SVG icon and symbolic icon featuring "Stilo" the stylus mascot.

---

## 🚀 Running Stilo Notes

### Direct Run (Development)
You can run Stilo Notes immediately without installing anything:
```bash
./run.py
```
or:
```bash
python3 run.py
```

---

## 🛠️ Building with Meson

Stilo Notes includes a complete, standard GNOME Meson build system:

```bash
# 1. Configure the build
meson setup _build --prefix=/usr/local

# 2. Compile and install
sudo ninja -C _build install

# 3. Launch
stilonotes
```

To run unit tests:
```bash
python3 -m unittest discover -s tests
```

---

## 📦 Flatpak

Stilo Notes is built with Flatpak support using the `org.gnome.Platform` and `org.gnome.Sdk` runtimes:

```bash
# Build and install Flatpak locally
./flatpak/build.sh
```

Or using `flatpak-builder` directly:
```bash
flatpak-builder --user --install --force-clean flatpak/build-dir flatpak/io.github.fastrizwaan.StiloNotes.yaml
```

Run the installed Flatpak:
```bash
flatpak run io.github.fastrizwaan.StiloNotes
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| <kbd>Ctrl</kbd> + <kbd>N</kbd> | Create a new note |
| <kbd>Ctrl</kbd> + <kbd>F</kbd> | Search notes |
| <kbd>Ctrl</kbd> + <kbd>\</kbd> | Toggle folder sidebar |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>D</kbd> | Toggle Dark / Light theme |
| <kbd>Esc</kbd> or <kbd>Alt</kbd> + <kbd>←</kbd> | Return to note list |
| <kbd>Ctrl</kbd> + <kbd>B</kbd> | Bold text |
| <kbd>Ctrl</kbd> + <kbd>I</kbd> | Italic text |
| <kbd>Tab</kbd> / <kbd>Shift</kbd> + <kbd>Tab</kbd> | Next / Previous table cell |
| <kbd>Ctrl</kbd> + <kbd>,</kbd> | Preferences |
| <kbd>Ctrl</kbd> + <kbd>?</kbd> | Shortcuts window |
| <kbd>Ctrl</kbd> + <kbd>Q</kbd> | Quit application |

---

## 📂 Project Architecture

```
StiloNotes/
├── assets/
│   ├── css/style.css                # GTK4 / Libadwaita custom styling
│   ├── editor/editor.html           # WebKit dynamic live Markdown editor template
│   └── icons/                       # Cute scalable and symbolic SVG icons
├── data/
│   ├── icons/                       # Standard hicolor icon paths
│   ├── io.github.fastrizwaan.StiloNotes.desktop.in
│   ├── io.github.fastrizwaan.StiloNotes.metainfo.xml.in
│   ├── io.github.fastrizwaan.StiloNotes.gschema.xml
│   └── meson.build
├── flatpak/
│   ├── build.sh                     # Flatpak build helper script
│   └── io.github.fastrizwaan.StiloNotes.yaml
├── build-aux/
│   ├── flatpak/io.github.fastrizwaan.StiloNotes.json
│   └── meson/post_install.py
├── po/                              # Gettext localization
├── stilonotes/                      # Core Python application package
│   ├── application.py               # Adw.Application, actions & dialogs
│   ├── config_manager.py            # Preferences and session state memory
│   ├── const.py                     # App constants & path resolution
│   ├── database.py                  # SQLite storage, categories & tasks
│   ├── editor.py                    # WebKit-based NoteEditor widget
│   ├── editor_html.py               # HTML template loader
│   ├── exporter.py                  # Export to Markdown, HTML, Plain text
│   ├── index.py                     # IndexView (OverlaySplitView with sidebar + list)
│   ├── main.py                      # Application entry point
│   ├── markdown_utils.py            # Two-way Markdown <-> HTML parser
│   ├── models.py                    # Note & Category dataclasses
│   ├── notes_list.py                # Note rows, cards, & multi-select list
│   ├── sidebar.py                   # Folder/category navigation sidebar
│   └── window.py                    # Adw.ApplicationWindow & NavigationView
├── tests/                           # Unit tests (models, database, markdown)
├── meson.build                      # Meson build system configuration
├── meson_options.txt                # Build options (profile, etc.)
└── run.py                           # Development launcher
```

---

## 📄 License

GPL-3.0-or-later © 2026 Mohammed Asif Ali Rizvan
