# Stilo Notes 🖊️

<p align="center">
  <img src="assets/icons/io.github.fastrizwaan.StiloNotes.svg" width="128" height="128" alt="Stilo Notes Icon">
</p>

<p align="center">
  <b>Elegant, distraction-free note taking for GNOME & Libadwaita.</b><br>
  Combines the clean, thoughtful architecture and UI of <a href="https://gitlab.gnome.org/World/iotas">Iotas</a> with the dynamic WebKit live Markdown-to-HTML rendering engine of <a href="https://github.com/fastrizwaan/TeddyNotes">TeddyNotes</a>.
</p>

<p align="center">
  <img src="https://github.com/fastrizwaan/StiloNotes/releases/download/1.0.0/stilonotes.png" alt="Stilo Notes Main Window" width="48%">
  <img src="https://github.com/fastrizwaan/StiloNotes/releases/download/1.0.0/Welcome.png" alt="Stilo Notes Welcome View" width="48%">
</p>


---

## ✨ Features

- **Distraction-Free & Standard View Modes**: Default distraction-free mode keeps your focus solely on writing by auto-hiding the sidebar, with instant toggle via <kbd>Ctrl+\</kbd> / <kbd>F11</kbd> or the option to keep the sidebar pinned in Preferences.
- **Custom Typography & Font Families**: Choose between System (Default), clean Sans-Serif, classic Serif, and developer Monospace typefaces with instant live preview.
- **Unified Text Zoom & Sizing**: Zoom notes smoothly from 80% to 160% in 10% steps, customize Card & List text size (Small, Normal, Large, Extra Large), and restore baseline settings anytime with a dedicated "Reset to Defaults" button.
- **Draggable Sidebar Splitter**: Smooth, flicker-free drag resizer between the sidebar and notes list with persistent width memory.
- **Category Hierarchy & Tag Popover**: Nested categories with inline [+] add button, collapsible chevrons, and dedicated Tags popover dropdown for quick tag filtering.
- **Dynamic WebKit Markdown Live Rendering**: Type standard and extended markdown syntax (`# `, `## `, `### `, `- [ ]`, `*`, `**`, `==highlight==`, `~~strike~~`, `~sub~`, `^super^`, `>`, ````lang````, `| a | b |`, `---`, emojis `:smile:`, and symbols `->`) and watch it dynamically transform into rich, beautifully styled interactive HTML on the fly.
- **List and Grid Views**: Toggle effortlessly between compact list view and visual note card grid view (`Ctrl+G`), with responsive FlowBox category sections.
- **Visual Note Cards**: Card previews show note titles, formatted excerpts, primary image thumbnails, and partial table previews with a clean, modern flat design.
- **Interactive Checklists**: Click checkboxes (`- [ ]` and `- [x]`) directly in the editor to toggle tasks and mark them completed.
- **Rich Formatting Toolbar**: Responsive FlowBox formatting bar that gracefully wraps on narrow windows, providing quick access to headings, bold, italic, strikethrough, underline, highlight, clear formatting, lists, tables, code blocks, links, and image insertion.
- **Table & Image Tools**: Insert tables with custom row/column counts, add/delete rows and columns, delete tables, insert images with aspect-ratio preserving resize handles, and link notes via titles.
- **Iotas-Inspired Clean UI**:
  - Distraction-free two-page navigation (`Adw.NavigationView`): Index and Editor.
  - Collapsible folder and category sidebar (`Adw.OverlaySplitView`).
  - Fast search with instant filtering across note titles, contents, and #tags.
  - Multi-selection mode for batch operations (export, duplicate, move, delete).
- **Multi-Window Support & Live Sync**: Open multiple windows (<kbd>Ctrl+Shift+N</kbd>) with real-time SQLite database change synchronization and concurrent conflict detection.
- **Trash Management & Empty State**: Dedicated "Empty Trash…" action bar and clean "Trash is Empty" state.
- **Smart Filters**: Quick sidebar filters for Favorites, Todos (notes containing checklists), Lists (bullet and numbered lists), and Recent notes.
- **Session Memory**: Remembers window geometry, view mode (list/grid), last active folder/category, and previously viewed note.
- **Real-Time Note Statistics**: Instant word count, character count, paragraph count, and reading time estimate.
- **Seamless Theme Sync**: Automatic synchronization with Libadwaita dark and light modes, with a manual quick-toggle.
- **Multiple Export Formats**: Export notes cleanly to Markdown (`.md`), HTML (`.html` with bundled base64 images), or Plain Text (`.txt`).
- **Cute Design & Mascot**: Includes custom Adwaita squircle SVG icon and symbolic icon featuring "Stilo" the stylus mascot.
- **Robust Architecture**: Thread-safe background database saving, zero UI freezes, and clean lifecycle management with zero memory leaks.

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
flatpak-builder --user --install --disable-rofiles-fuse --force-clean flatpak/build-dir flatpak/io.github.fastrizwaan.StiloNotes.yaml
```

Run the installed Flatpak:
```bash
flatpak run io.github.fastrizwaan.StiloNotes
```

### Flatpak bundle
```bash
flatpak build-bundle ~/.local/share/flatpak/repo io.github.fastrizwaan.StiloNotes.flatpak io.github.fastrizwaan.StiloNotes

```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| <kbd>Ctrl</kbd> + <kbd>N</kbd> | Create a new note |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>N</kbd> | Open a new window |
| <kbd>Ctrl</kbd> + <kbd>F</kbd> | Search notes |
| <kbd>Ctrl</kbd> + <kbd>G</kbd> | Toggle List / Grid view |
| <kbd>Ctrl</kbd> + <kbd>\</kbd> | Toggle folder sidebar |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>D</kbd> | Toggle Dark / Light theme |
| <kbd>Esc</kbd> or <kbd>Alt</kbd> + <kbd>←</kbd> | Return to note list |
| <kbd>Ctrl</kbd> + <kbd>B</kbd> | Bold text |
| <kbd>Ctrl</kbd> + <kbd>I</kbd> | Italic text |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>H</kbd> | Highlight text |
| <kbd>Ctrl</kbd> + <kbd>Z</kbd> / <kbd>Ctrl</kbd> + <kbd>Y</kbd> | Undo / Redo |
| <kbd>Ctrl</kbd> + <kbd>+</kbd> / <kbd>Ctrl</kbd> + <kbd>-</kbd> / <kbd>Ctrl</kbd> + <kbd>0</kbd> | Zoom in / Zoom out / Reset font size |
| <kbd>Tab</kbd> / <kbd>Shift</kbd> + <kbd>Tab</kbd> | Next / Previous table cell or indent |
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
│   ├── category_header_bar.py       # Category header and filter widgets
│   ├── config_manager.py            # Preferences and session state memory
│   ├── const.py                     # App constants & path resolution
│   ├── database.py                  # SQLite storage, categories & tasks
│   ├── editor.py                    # WebKit-based NoteEditor widget
│   ├── editor_html.py               # HTML template loader
│   ├── exporter.py                  # Export to Markdown, HTML, Plain text
│   ├── font_size_selector.py        # Font size adjustment widget
│   ├── index.py                     # IndexView (OverlaySplitView with sidebar + list/grid)
│   ├── main.py                      # Application entry point
│   ├── markdown_utils.py            # Two-way Markdown <-> HTML parser
│   ├── models.py                    # Note & Category dataclasses
│   ├── notes_list.py                # Note rows, grid cards, & FlowBox views
│   ├── selection_header_bar.py      # Batch selection mode headerbar
│   ├── sidebar.py                   # Folder/category navigation sidebar
│   ├── theme_selector.py            # Light/Dark/Follow system theme selector
│   └── window.py                    # Adw.ApplicationWindow & NavigationView
├── tests/                           # Unit tests (models, database, markdown, widgets)
├── meson.build                      # Meson build system configuration
├── meson_options.txt                # Build options (profile, etc.)
└── run.py                           # Development launcher
```

---

## 📄 License

GPL-3.0-or-later © 2026 Mohammed Asif Ali Rizvan
