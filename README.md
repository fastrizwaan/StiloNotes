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

### ✍️ Rich Live Markdown Editor
- **Dynamic WebKit Markdown Live Rendering**: Type standard and extended markdown syntax and watch it dynamically transform into rich, beautifully styled interactive HTML on the fly.
- **Full CommonMark Compliance**: Strict adherence to the CommonMark specification, including complete support for nested inline styling (bold, italic, underscores), ordered list parenthesis markers (e.g. `1)`), ATX headings, and flawless backslash character escaping.
- **Extensive Syntax Support**: Bold, italic, code spans, lists, quotes, tables, wiki links (`[[link]]`), hashtags (`#tag`), category badges (`##category`), and mentions (`@user`).
- **Interactive Checklists**: Click checkboxes (`- [ ]` and `- [x]`) directly in the editor to toggle tasks and track completion status in real time.
- **Smart Link Insertion**: Two-entry "Insert Link" dialog (<kbd>Ctrl</kbd>+<kbd>K</kbd>) prefilled with your active selection, plus <kbd>Ctrl</kbd>+Click to open links externally in your default browser.
- **Responsive FlowBox Formatting Toolbar**: A modern toolbar providing quick access to headings, bold, italic, strikethrough, underline, marker highlight, inline code, code blocks, bullet/numbered lists, tables, links, and image insertion.
- **Table & Image Insertion**: Insert tables with customizable row and column counts, add/delete rows and columns, delete tables, and insert images with aspect-ratio preserving resize handles.
- **Read-Only Protection & One-Click Edit Mode**: Existing notes automatically open in safe read-only mode to prevent accidental edits or alterations. A dedicated Edit button (<kbd>Ctrl</kbd>+<kbd>E</kbd>) in the header bar unlocks editing instantly.
- **Sequential Untitled Counter**: Newly created untitled notes are numbered sequentially (`Untitled Note 1`, `Untitled Note 2`...), preventing duplicates and smartly filling gaps.
- **Real-Time Note Statistics**: Instant live updates for word count, character count, paragraph count, and estimated reading time.
- **Seamless HTML Roundtrip**: Automatically and accurately converts your live rich text back into clean, portable Markdown syntax when saving to the database.

### 📄 Professional Page Setup & Printing
- **Page Setup Dialog (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>)**: Configure page dimensions, orientation, and margins with persistent settings saved to your user preferences.
- **Standard Paper Sizes**: Built-in support for ISO A4, US Letter, US Legal, Executive, A3, A5, and B5 paper sizes.
- **Orientation & Custom Margins**: Switch between Portrait and Landscape orientations, with custom margins configurable in Inches (`in`), Millimeters (`mm`), Centimeters (`cm`), or Points (`pt`).
- **WebKit Portal Printing (<kbd>Ctrl</kbd>+<kbd>P</kbd>)**: Print directly or export to PDF with live print preview using the XDG Desktop Portal Print dialog.

### 🔢 Smart Organization & Categorization
- **Nested Categories & Collapsible Chevrons**: Organize notes in multi-level folder hierarchies with an inline `+` category button, collapsible chevrons, and full-width auto-suggest dropdown.
- **Drag-and-Drop Reordering**: Rearrange your sidebar categories natively using drag-and-drop to customize your workflow, with persistent database ordering.
- **Hashtags & Tag Popover**: Type `#tag` directly into note content with autocomplete suggestions, clickable tag pills, and a dedicated Tags popover dropdown for fast filtering.
- **List & Visual Grid Views (<kbd>Ctrl</kbd>+<kbd>G</kbd>)**: Switch between a compact note list and a visual note card grid with responsive FlowBox category sections.
- **Visual Note Cards**: Card previews display note titles, formatted excerpts, primary image thumbnails, and partial table previews with a clean, borderless design.
- **Smart Sidebar Filters**: One-click filters for All Notes, Favorites, Todos (checklist notes), Lists (bullet & numbered lists), Private Notes, and Trash.
- **Instant Search (<kbd>Ctrl</kbd>+<kbd>F</kbd>)**: Lightning-fast instant search across note titles, body contents, and tags.
- **Batch Selection Mode**: Select multiple notes to bulk export, duplicate, assign categories, or delete.

### 🔒 Privacy, Security & Backup
- **Private & Password-Secured Notes**: Protect confidential notes with PBKDF2-SHA256 salted AES-256 encryption, session locking, dedicated sidebar section, and hidden search/selection states when locked.
- **Local Database Backup & Standalone GPG**: Export clean SQLite snapshots or encrypt them with AES-256 password protection via standalone GPG (`.db.gpg`) without touching system keyrings. Supports one-click restore.
- **Automated Backup on Exit**: Optional automatic backups on application exit to a configurable destination folder.
- **Hardened Codebase**: Lazy module loading, zero plaintext persistence of backup passwords, and HTML-escaping sanitization.

### 🎨 GNOME Experience & Customization
- **Iotas-Inspired Clean UI**: Distraction-free two-page navigation (`Adw.NavigationView`): Index and Editor, with adaptive overlays (`Adw.OverlaySplitView`).
- **Distraction-Free & Standard Modes**: Auto-hides the sidebar when editing for maximum focus, with instant toggle via <kbd>Ctrl</kbd>+<kbd>\</kbd> / <kbd>F11</kbd> or an option to keep the sidebar pinned.
- **Custom Typography**: Choose between System (Default), clean Sans-Serif, classic Serif, and developer Monospace typefaces with live preview.
- **Unified Text Zoom & Sizing**: Zoom notes smoothly from 80% to 160%, customize Card & List text size (Small, Normal, Large, Extra Large), and restore defaults anytime.
- **Draggable Sidebar Splitter**: Smooth, flicker-free drag resizer between the sidebar and notes list with persistent width memory.
- **Dark & Light Mode Sync**: Seamless synchronization with Libadwaita dark and light themes, plus a manual toggle shortcut (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>D</kbd>).
- **Multi-Window Support (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>N</kbd>)**: Open multiple windows with real-time SQLite database change synchronization and concurrent conflict detection.
- **Multiple Import & Export Formats**: Open external `.md` and `.txt` files directly (<kbd>Ctrl</kbd>+<kbd>O</kbd>), or export notes cleanly to Markdown (`.md`), HTML (`.html` with bundled base64 images), or Plain Text (`.txt`).
- **Cute Mascot**: Custom Adwaita squircle icon featuring "Stilo" the stylus mascot.

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
| <kbd>Ctrl</kbd> + <kbd>E</kbd> | Edit note / unlock editing mode |
| <kbd>Ctrl</kbd> + <kbd>O</kbd> | Open note from file (.md, .txt) |
| <kbd>Ctrl</kbd> + <kbd>P</kbd> | Print note (WebKit print portal) |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd> | Page Setup dialog |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>N</kbd> | Open a new window |
| <kbd>Ctrl</kbd> + <kbd>F</kbd> | Search notes |
| <kbd>Ctrl</kbd> + <kbd>G</kbd> | Toggle List / Grid view |
| <kbd>Ctrl</kbd> + <kbd>\</kbd> | Toggle folder sidebar |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>D</kbd> | Toggle Dark / Light theme |
| <kbd>Esc</kbd> or <kbd>Alt</kbd> + <kbd>←</kbd> | Return to note list |
| <kbd>Ctrl</kbd> + <kbd>B</kbd> | Bold text |
| <kbd>Ctrl</kbd> + <kbd>I</kbd> | Italic text |
| <kbd>Ctrl</kbd> + <kbd>K</kbd> | Insert link / Edit link |
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
│   ├── backup_encryption.py         # Standalone GPG symmetric backup encryption
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
│   ├── page_setup.py                # Page setup dialog, paper sizes & margin configs
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
