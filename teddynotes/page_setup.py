# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Page Setup dialog and helpers for Teddy Notes.
Provides paper size, orientation, and margin configuration for printing and export.
Directly adapted from WebkitWord sources.
"""

from typing import Optional, Callable
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib

PAPER_NAMES = [
    ("A4", Gtk.PAPER_NAME_A4),
    ("US Letter", Gtk.PAPER_NAME_LETTER),
    ("Legal", Gtk.PAPER_NAME_LEGAL),
    ("A3", Gtk.PAPER_NAME_A3),
    ("A5", Gtk.PAPER_NAME_A5),
]

FACTORS = {
    "in": 72.0,
    "mm": 72.0 / 25.4,
    "cm": 72.0 / 2.54,
    "pt": 1.0,
}

BOUNDS = {
    "in": (0.0, 5.0, 0.05),
    "mm": (0.0, 100.0, 1.0),
    "cm": (0.0, 10.0, 0.1),
    "pt": (0.0, 300.0, 1.0),
}

UNITS_LIST = [
    ("inches (in)", "in"),
    ("millimeters (mm)", "mm"),
    ("centimeters (cm)", "cm"),
    ("points (pt)", "pt"),
]


def from_points(val: float, unit: str) -> float:
    """Convert points to specified unit."""
    return val / FACTORS.get(unit, 1.0)


def to_points(val: float, unit: str) -> float:
    """Convert value in specified unit to points."""
    return val * FACTORS.get(unit, 1.0)


def create_default_page_setup() -> Gtk.PageSetup:
    """Create default page setup with A4 paper and standard 1-inch margins."""
    page_setup = Gtk.PageSetup.new()
    paper_size = Gtk.PaperSize.new(Gtk.PAPER_NAME_A4)
    page_setup.set_paper_size(paper_size)
    page_setup.set_orientation(Gtk.PageOrientation.PORTRAIT)
    # Default 1-inch (72 pt) margins
    page_setup.set_top_margin(72.0, Gtk.Unit.POINTS)
    page_setup.set_right_margin(72.0, Gtk.Unit.POINTS)
    page_setup.set_bottom_margin(72.0, Gtk.Unit.POINTS)
    page_setup.set_left_margin(72.0, Gtk.Unit.POINTS)
    return page_setup


def show_page_setup_dialog(
    parent_window: Optional[Gtk.Window],
    current_page_setup: Optional[Gtk.PageSetup] = None,
    current_unit: str = "in",
    on_applied: Optional[Callable[[Gtk.PageSetup, str], None]] = None,
):
    """Show page setup dialog for configuring paper size, orientation, and margins.

    Directly adapted from WebkitWord Page Setup dialog.
    """
    if current_page_setup is None:
        current_page_setup = create_default_page_setup()

    use_adw_dialog = hasattr(Adw, "Dialog")
    if use_adw_dialog:
        dialog = Adw.Dialog()
        dialog.set_title("Page Setup")
        dialog.set_content_width(400)
    else:
        dialog = Gtk.Window()
        dialog.set_title("Page Setup")
        dialog.set_default_size(400, -1)
        dialog.set_modal(True)
        if parent_window:
            dialog.set_transient_for(parent_window)

    content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    content_box.set_margin_top(24)
    content_box.set_margin_bottom(24)
    content_box.set_margin_start(24)
    content_box.set_margin_end(24)

    header_label = Gtk.Label()
    header_label.set_markup("<b>Page Options</b>")
    header_label.set_halign(Gtk.Align.START)
    content_box.append(header_label)

    # 1. Paper size
    paper_size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    paper_size_label = Gtk.Label(label="Paper Size:")
    paper_size_label.set_halign(Gtk.Align.START)
    paper_size_label.set_hexpand(True)

    paper_string_list = Gtk.StringList()
    for display_name, _ in PAPER_NAMES:
        paper_string_list.append(display_name)
    paper_size_dropdown = Gtk.DropDown.new(paper_string_list, None)

    # Detect current paper size index
    selected_paper_index = 0
    if current_page_setup:
        ps = current_page_setup.get_paper_size()
        pname = ps.get_name().lower() if ps else "iso_a4"
        for i, (dname, gname) in enumerate(PAPER_NAMES):
            if pname == gname.lower() or pname == dname.lower() or (dname == "US Letter" and "letter" in pname):
                selected_paper_index = i
                break

    paper_size_dropdown.set_selected(selected_paper_index)
    paper_size_box.append(paper_size_label)
    paper_size_box.append(paper_size_dropdown)
    content_box.append(paper_size_box)

    # 2. Orientation
    orientation_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    orientation_label = Gtk.Label(label="Orientation:")
    orientation_label.set_halign(Gtk.Align.START)
    orientation_label.set_hexpand(True)

    portrait_radio = Gtk.CheckButton(label="Portrait")
    landscape_radio = Gtk.CheckButton(label="Landscape")
    landscape_radio.set_group(portrait_radio)

    if current_page_setup:
        is_landscape = (current_page_setup.get_orientation() == Gtk.PageOrientation.LANDSCAPE)
        portrait_radio.set_active(not is_landscape)
        landscape_radio.set_active(is_landscape)
    else:
        portrait_radio.set_active(True)

    orientation_box.append(orientation_label)
    orientation_box.append(portrait_radio)
    orientation_box.append(landscape_radio)
    content_box.append(orientation_box)

    # 3. Margins
    margins_label = Gtk.Label()
    margins_label.set_markup("<b>Margins</b>")
    margins_label.set_halign(Gtk.Align.START)
    margins_label.set_margin_top(16)
    content_box.append(margins_label)

    # Unit dropdown
    units_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    units_box.set_margin_start(12)
    units_label = Gtk.Label(label="Units:")
    units_label.set_halign(Gtk.Align.START)

    units_string_list = Gtk.StringList()
    for display_u, _ in UNITS_LIST:
        units_string_list.append(display_u)
    units_dropdown = Gtk.DropDown.new(units_string_list, None)

    active_unit_idx = 0
    for i, (_, code) in enumerate(UNITS_LIST):
        if code == current_unit:
            active_unit_idx = i
            break
    units_dropdown.set_selected(active_unit_idx)
    units_dropdown.current_unit = current_unit

    units_box.append(units_label)
    units_box.append(units_dropdown)
    content_box.append(units_box)

    # Helper to create spin button
    def make_spin(unit_code: str):
        low, high, step = BOUNDS[unit_code]
        adj = Gtk.Adjustment.new(1.0, low, high, step, step * 5, 0.0)
        spin = Gtk.SpinButton()
        spin.set_adjustment(adj)
        digits = 0 if unit_code == "pt" else (1 if unit_code in ("mm", "cm") else 2)
        spin.set_digits(digits)
        return spin, adj

    unit_code = units_dropdown.current_unit
    top_spin, top_adj = make_spin(unit_code)
    right_spin, right_adj = make_spin(unit_code)
    bottom_spin, bottom_adj = make_spin(unit_code)
    left_spin, left_adj = make_spin(unit_code)

    # Set initial margin values
    if current_page_setup:
        top_pt = current_page_setup.get_top_margin(Gtk.Unit.POINTS)
        right_pt = current_page_setup.get_right_margin(Gtk.Unit.POINTS)
        bottom_pt = current_page_setup.get_bottom_margin(Gtk.Unit.POINTS)
        left_pt = current_page_setup.get_left_margin(Gtk.Unit.POINTS)
    else:
        top_pt = right_pt = bottom_pt = left_pt = 72.0

    top_spin.set_value(from_points(top_pt, unit_code))
    right_spin.set_value(from_points(right_pt, unit_code))
    bottom_spin.set_value(from_points(bottom_pt, unit_code))
    left_spin.set_value(from_points(left_pt, unit_code))

    def on_unit_changed(dropdown, _param):
        old_u = dropdown.current_unit
        new_u = UNITS_LIST[dropdown.get_selected()][1]

        for spin, adj in ((top_spin, top_adj), (right_spin, right_adj),
                          (bottom_spin, bottom_adj), (left_spin, left_adj)):
            pts = to_points(spin.get_value(), old_u)
            low, high, step = BOUNDS[new_u]
            adj.set_lower(low)
            adj.set_upper(high)
            adj.set_step_increment(step)
            digits = 0 if new_u == "pt" else (1 if new_u in ("mm", "cm") else 2)
            spin.set_digits(digits)
            spin.set_value(from_points(pts, new_u))

        dropdown.current_unit = new_u

    units_dropdown.connect("notify::selected", on_unit_changed)

    # Layout margin grid
    margins_grid = Gtk.Grid()
    margins_grid.set_row_spacing(8)
    margins_grid.set_column_spacing(12)
    margins_grid.set_margin_start(12)

    labels_spins = [
        ("Top:", top_spin),
        ("Right:", right_spin),
        ("Bottom:", bottom_spin),
        ("Left:", left_spin),
    ]

    for idx, (lbl, spin) in enumerate(labels_spins):
        l = Gtk.Label(label=lbl)
        l.set_halign(Gtk.Align.START)
        margins_grid.attach(l, 0, idx, 1, 1)
        margins_grid.attach(spin, 1, idx, 1, 1)

    content_box.append(margins_grid)

    # 4. Buttons
    button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    button_box.set_halign(Gtk.Align.END)
    button_box.set_margin_top(24)

    cancel_btn = Gtk.Button(label="Cancel")
    apply_btn = Gtk.Button(label="Apply")
    apply_btn.add_css_class("suggested-action")

    def on_close():
        if use_adw_dialog:
            dialog.close()
        else:
            dialog.destroy()

    def on_apply(_btn):
        idx = paper_size_dropdown.get_selected()
        paper_name = PAPER_NAMES[idx][1]

        orient = Gtk.PageOrientation.LANDSCAPE if landscape_radio.get_active() else Gtk.PageOrientation.PORTRAIT

        unit = units_dropdown.current_unit
        top_margin = to_points(top_spin.get_value(), unit)
        right_margin = to_points(right_spin.get_value(), unit)
        bottom_margin = to_points(bottom_spin.get_value(), unit)
        left_margin = to_points(left_spin.get_value(), unit)

        page_setup = Gtk.PageSetup.new()
        page_setup.set_paper_size(Gtk.PaperSize.new(paper_name))
        page_setup.set_orientation(orient)
        page_setup.set_top_margin(top_margin, Gtk.Unit.POINTS)
        page_setup.set_right_margin(right_margin, Gtk.Unit.POINTS)
        page_setup.set_bottom_margin(bottom_margin, Gtk.Unit.POINTS)
        page_setup.set_left_margin(left_margin, Gtk.Unit.POINTS)

        on_close()

        if on_applied:
            on_applied(page_setup, unit)

    apply_btn.connect("clicked", on_apply)
    cancel_btn.connect("clicked", lambda _b: on_close())
    button_box.append(cancel_btn)
    button_box.append(apply_btn)
    content_box.append(button_box)

    if use_adw_dialog:
        dialog.set_child(content_box)
        dialog.present(parent_window)
    else:
        dialog.set_child(content_box)
        dialog.present()
