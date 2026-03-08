"""
This file contains the ScanWindow class, which manages the student attendance scanning process.

The "Focus View" feature has been redesigned into a modern, Material 3-style interface
to provide a guided, conversational user experience. All changes for this redesign are
encapsulated within this file, primarily in the `scan_focus_` prefixed methods.
"""
import os
from datetime import datetime
from tkinter import messagebox, ttk

import customtkinter as ctk
import pandas as pd
from customtkinter import CTkButton, CTkEntry, CTkFrame, CTkLabel, CTkProgressBar, CTkTextbox, CTkToplevel
from PIL import Image

from core.focus_view_state import build_focus_view_state
from core.grade_logic import grade_missing_or_zero
from core.scan_filters import FILTER_DEFAULTS, apply_task_filter_change, clear_filter_values, is_filter_active
from core.scan_workflow import (
    append_notes,
    build_focus_action_payload,
    build_manual_add_default_notes,
    describe_tasks,
    format_column_timestamp,
    format_note_tag,
)
from core.session_mutations import build_manual_add_record, build_record_payload, prepare_attendance_update
from core.scan_view_logic import build_scan_context, collect_missing_tasks, determine_scan_status, row_matches_filters
from ui.components.scan_filter_panel import ScanFilterPanel
from ui.components.scan_stats_strip import ScanStatsStrip
from ui.dialogs.add_student_dialog import AddStudentDialog
from ui.dialogs.confirmation_dialog import ConfirmationDialog
from utils.helpers import (
    ASSETS_DIR,
    HOME_BG_FILE,
    MIN_SCAN_SIZE,
    SESSION_LAST_ACTION_COL,
    SESSION_MANUAL_ADDED_COL,
    bring_window_to_front,
    compute_session_summary,
    ensure_initial_size,
    read_data,
    set_dark_title_bar,
)
from .focus_view_window import FocusViewWindow, PLACEHOLDER_TEXT

# Located at the top of scan_window.py, after the other imports

# +++ FINAL DEFINITIVE VERSION - REPLACE THE PREVIOUS BLOCK WITH THIS +++
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    def _process_arabic(text):
        """A helper that reshapes and reorders Arabic text."""
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)

except ImportError:
    print("WARNING: Arabic text support is limited. Please run: pip install arabic_reshaper python-bidi")
    # If libraries are missing, create a dummy function that does nothing.
    _process_arabic = lambda text: text

def _format_arabic_text(text):
    """
    Correctly formats Arabic text for display in the UI.
    It checks for Arabic characters before processing.
    """
    if not text:
        return text
    
    text_str = str(text)
    # Only process strings that contain Arabic characters to avoid errors.
    if not any('\u0600' <= char <= '\u06FF' for char in text_str):
        return text_str
    
    return _process_arabic(text_str)

def get_font_for_text(text):
    """Returns 'Noto Sans Arabic' if text contains Arabic, otherwise 'Roboto'."""
    text_str = str(text)
    if any('\u0600' <= char <= '\u06FF' for char in text_str):
        return "Noto Sans Arabic"
    return "Roboto"

# --- Constants for the new Focus View Design ---
# Label used when a student is added from a different group
DIFF_GROUP_NOTE = "(From diff Group)"

# Dark Mode
DARK_BG = "#1d1b20"
DARK_SURFACE = "#141218"
DARK_PRIMARY_TEXT = "#e3e2e6"
DARK_SECONDARY_TEXT = "#cac4d0"
DARK_SUCCESS = "#b5d3a7"
DARK_WARNING = "#f9d694"
DARK_ERROR = "#f2b8b5"
DARK_INFO = "#a9c8e7"

AUTO_ATTEND_SUCCESS_TAG = "auto_attend_success"
AUTO_ATTEND_FLASH_BG = "#244b31"
AUTO_ATTEND_FLASH_FG = "#ffffff"
AUTO_ATTEND_FLASH_DURATION_MS = 900
SESSION_SAVE_DEBOUNCE_MS = 800

class ScanWindow(CTkToplevel):
    def _reset_treeview_sort(self):
        """Restore Treeview rows to their original order."""
        self._tree_sort_column = None
        self._tree_sort_reverse = False
        # Detach all
        for iid in self._all_iids:
            if self.tree.exists(iid):
                self.tree.detach(iid)
        # Re-attach in original order
        for iid in self._all_iids:
            if self.tree.exists(iid):
                self.tree.reattach(iid, '', 'end')

    def __init__(self, parent, session_mgr, read_only=False):
        super().__init__(parent)
        set_dark_title_bar(self)
        self.parent = parent
        self.sm = session_mgr
        self.read_only = read_only
        self.state('zoomed')
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.toggle_fullscreen)
        self.bind("<Control-KeyPress>", self._on_ctrl_keypress)
        self.restrictions = self.sm.restrictions
        self.df = read_data(self.sm.session_path).fillna("")
        self.mapping = self.sm.mapping or {col: col for col in self.df.columns}

        # --- Icon Cache ---
        self._icon_cache = {}

        # --- Filter State ---
        self._filter_panel = None
        self._filter_vars = {
            "attendance": ctk.StringVar(value=FILTER_DEFAULTS["attendance"]),
            "missing_exam": ctk.BooleanVar(value=FILTER_DEFAULTS["missing_exam"]),
            "missing_hw": ctk.BooleanVar(value=FILTER_DEFAULTS["missing_hw"]),
            "has_exam": ctk.BooleanVar(value=FILTER_DEFAULTS["has_exam"]),
            "has_hw": ctk.BooleanVar(value=FILTER_DEFAULTS["has_hw"]),
            "has_notes": ctk.BooleanVar(value=FILTER_DEFAULTS["has_notes"]),
            "manual_added": ctk.BooleanVar(value=FILTER_DEFAULTS["manual_added"]),
        }
        self._filter_active = False

        self.title("Scan Attendance")
        self.protocol("WM_DELETE_WINDOW", self._on_end_scan)
        self.after(50, lambda: bring_window_to_front(self))

        # --- Instance Variables ---
        self._all_iids = []
        self._search_entries = []
        self.search_var = None
        self._focus_reset_job = None
        self._focus_guard_depth = 0
        self.scan_focus_ctx = None
        self.scan_focus_visible_cache = []
        self.scan_focus_timer = None
        self.focus_view_container = None # For integrated view
        self._row_flash_jobs = {}
        self._notes_placeholder_active = False
        self._pending_session_save_job = None
        self.stats_strip = None

        self._build_ui()
        self._apply_treeview_style()
        self._load_existing()
        self._refresh_stats()
        ensure_initial_size(self, min_size=MIN_SCAN_SIZE)

        if not self.read_only:
            self.bind_all("<FocusIn>", self._global_focus_in, add="+")
            self.scan_entry.focus_set()

    def _on_filter_click(self):
        # Toggle filter panel visibility
        if self._filter_panel and self._filter_panel.winfo_exists():
            self._hide_filter_panel()
        else:
            self._show_filter_panel()

    def _show_filter_panel(self):
        # Create panel if not exists
        if self._filter_panel and self._filter_panel.winfo_exists():
            self._filter_panel.lift()
            return
        panel_width = 320
        panel = ScanFilterPanel(
            self,
            filter_vars=self._filter_vars,
            load_icon=self._load_icon,
            on_hide=self._hide_filter_panel,
            on_filter_change=self._on_filter_change,
            on_task_filter_change=self._on_task_filter_change,
            on_clear_filters=self._clear_filters,
            panel_width=panel_width,
        )
        self._filter_panel = panel
        self.update_idletasks()
        # Center panel horizontally above filter icon
        bx = self.filter_button.winfo_rootx()
        by = self.filter_button.winfo_rooty() + self.filter_button.winfo_height()
        icon_width = self.filter_button.winfo_width()
        x = bx - self.winfo_rootx() + (icon_width // 2) - (panel_width // 2)
        y = by - self.winfo_rooty()
        panel.place(x=x, y=y)

        self._filter_panel.lift()

    def _hide_filter_panel(self):
        if self._filter_panel and self._filter_panel.winfo_exists():
            self._filter_panel.place_forget()
            self._filter_panel.destroy()

    def _on_click_away(self, event):
        pass  # Removed click-away dismissal for filter panel

    def _on_filter_change(self):
        self._filter_active = self._is_filter_active()
        self._update_filter_icon()
        self._filter_all()

    def _get_filter_values(self):
        values = {}
        for key, var in self._filter_vars.items():
            values[key] = var.get()
        return values

    def _set_filter_values(self, values):
        for key, value in values.items():
            if key in self._filter_vars:
                self._filter_vars[key].set(value)

    def _on_task_filter_change(self, task_type, state):
        """Handles mutually exclusive checkbox logic for tasks."""
        updated = apply_task_filter_change(self._get_filter_values(), task_type, state)
        self._set_filter_values(updated)
        self._on_filter_change()

    def _clear_filters(self):
        self._set_filter_values(clear_filter_values(self._get_filter_values()))
        self._filter_active = False
        self._update_filter_icon()
        self._filter_all()
        self._hide_filter_panel()

    def _is_filter_active(self):
        return is_filter_active(self._get_filter_values())

    def _update_filter_icon(self):
        # Change icon to filled if filter active
        icon_name = "filter.png" if not self._filter_active else "filter_filled.png"
        self.filter_button.configure(image=self._load_icon(icon_name, size=(28, 28)))

    def toggle_fullscreen(self, event=None):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))


    # --------------------------------------------------------------------------
    # Redesigned Focus View (Material 3 Style)
    # --------------------------------------------------------------------------

    def _load_icon(self, name, size=(24, 24)):
        """
        Loads an icon from the assets directory and caches it.
        Icons are expected to be white for proper coloring.
        """
        if (name, size) in self._icon_cache:
            return self._icon_cache[(name, size)]
        
        try:
            img_path = os.path.join(ASSETS_DIR, name)
            img = Image.open(img_path)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
            self._icon_cache[(name, size)] = ctk_img
            return ctk_img
        except FileNotFoundError:
            print(f"Warning: Icon '{name}' not found at '{ASSETS_DIR}'")
            # Return a placeholder transparent image
            return ctk.CTkImage(light_image=Image.new("RGBA", size, (0,0,0,0)),
                                dark_image=Image.new("RGBA", size, (0,0,0,0)),
                                size=size)

    def scan_focus_create_ui(self, parent):
        """
        Creates the Focus View UI using FocusViewWindow class.
        """
        self.focus_view = FocusViewWindow(
            parent,
            read_only=getattr(self, 'read_only', False),
            icon_cache=getattr(self, '_icon_cache', {}),
            on_complete=self.scan_focus_on_completed,
            on_add_student=self.scan_focus_on_add_student,
            on_override=self.scan_focus_on_override,
            on_save_notes=self._handle_notes_save,
            on_deny=self.scan_focus_on_deny,
            on_cancel=self.scan_focus_on_cancel_attendance,
            on_dismiss=self._handle_focus_dismiss_request
        )

        # Bind Arabic-specific shortcuts to the notes widget
        # Ctrl+ش (Arabic for 'A') should trigger "Select All"
        self.focus_view.notes.bind("<Control-KeyPress>", self._on_notes_ctrl_keypress)

    def _on_ctrl_keypress(self, event):
        """Handles global Ctrl key-presses for cross-language compatibility."""
        # For Ctrl+S (focus scan entry) - Arabic 'س'
        if event.char.lower() in ('s', 'س'):
            focused_widget = self.focus_get()
            if isinstance(focused_widget, (CTkEntry, CTkTextbox)):
                return  # Don't steal focus if the user is typing
            self.scan_entry.focus_set()
            return "break"
        return None

    def _on_notes_ctrl_keypress(self, event):
        """Handles Ctrl key-presses in the notes widget for special characters."""
        char = event.char.lower()
        widget = event.widget

        # Select All: Ctrl+A (English) or Ctrl+ش (Arabic)
        if char in ('a', 'ش'):
            self.focus_view.notes._textbox.tag_add("sel", "1.0", "end")
            return "break"  # Prevents the character from being inserted
        # Copy: Ctrl+C (English) or Ctrl+ؤ (Arabic)
        elif char in ('c', 'ؤ'):
            widget.event_generate("<<Copy>>")
            return "break"
        # Paste: Ctrl+V (English) or Ctrl+ر (Arabic)
        elif char in ('v', 'ر'):
            widget.event_generate("<<Paste>>")
            return "break"
        
    def _on_notes_focus_in(self, event):
        self._pause_focus_guard()
        if self._notes_placeholder_active:
            self.focus_view.notes.delete("1.0", "end")
            self.focus_view.notes.configure(text_color=DARK_PRIMARY_TEXT)
            self._notes_placeholder_active = False

    def _on_notes_focus_out(self, event):
        self._resume_focus_guard()
        if not self.focus_view.notes.get("1.0", "end-1c"):
            self.focus_view.notes.configure(text_color="gray")
            self.focus_view.notes.insert("1.0", "Add notes here...")
            self._notes_placeholder_active = True

    def scan_focus_show(self, scan_ctx):
        """Shows and populates the Focus View with student data."""
        self._persist_active_focus_notes()
        self.scan_focus_cancel_timer()
        if not self.focus_view_container: return

        # Show the integrated focus view panel
        self.focus_view_container.grid()
        
        ctx = dict(scan_ctx or {})
        ctx.setdefault("original_notes", ctx.get("existing_notes", ""))
        self.scan_focus_ctx = ctx
        
        status = ctx.get("status") or self.scan_determine_status(ctx)
        ctx["status"] = status

        # Populate UI elements
        student_name = ctx.get("name") or "Unknown Student"
        formatted_name = _format_arabic_text(student_name)
        card_display_val = ctx.get('card_display', '') or ''
        card_display = str(card_display_val).replace('null', '').strip() or '--'
        student_id_val = ctx.get('student_id', '') or ''
        student_id = str(student_id_val).replace('null', '').strip() or '--'
        self.focus_view.set_student_identity(
            formatted_name,
            get_font_for_text(student_name),
            student_id,
            card_display,
        )

        # Set notes
        existing_notes = ctx.get("existing_notes", "")
        self._notes_placeholder_active = self.focus_view.set_notes_content(
            existing_notes,
            formatted_notes=_format_arabic_text(existing_notes) if existing_notes else "",
            is_rtl=any('\u0600' <= char <= '\u06FF' for char in str(existing_notes)),
        )

        # Filter the main table view
        focus_iids = ctx.get("focus_iids") or []
        if focus_iids and not ctx.get("skip_filter") and ctx.get("iid") is not None:
            self.scan_filter_for_focus(focus_iids)
        else:
            if focus_iids:
                primary = focus_iids[0]
                if self.tree.exists(primary):
                    self.tree.selection_set(primary); self.tree.focus(primary)
            self.scan_restore_from_focus()

        # Set status and update dynamic UI parts
        self.focus_view.render_status(build_focus_view_state(status, ctx))

    def scan_focus_clear(self):
        """Hides the Focus View and resets its state."""
        self.scan_focus_cancel_timer()
        self.scan_focus_ctx = None
        
        if hasattr(self, "focus_view"):
            self.focus_view.reset_view()
            self._notes_placeholder_active = True

        self.scan_restore_from_focus()
        
        if self.focus_view_container:
            self.focus_view_container.grid_remove()
            
        self.after(120, self.scan_entry.focus_set)

    # --------------------------------------------------------------------------
    # Original ScanWindow methods (unchanged unless necessary for integration)
    # --------------------------------------------------------------------------

    def _on_bg_resize(self, event):
        pass  # No background image to resize

    def _focus_scan_entry(self):
        self._focus_reset_job = None
        if self.read_only or self._focus_guard_depth > 0: return
        try: self.scan_entry.focus_set() 
        except Exception: pass

    def _pause_focus_guard(self):
        if self._focus_reset_job is not None:
            try: self.after_cancel(self._focus_reset_job)
            except Exception: pass
            self._focus_reset_job = None
        self._focus_guard_depth += 1

    def _resume_focus_guard(self):
        if self._focus_guard_depth > 0: self._focus_guard_depth -= 1


    def _build_ui(self):
        # --- Header Bar ---
        top_bar = CTkFrame(self, fg_color="#1d1b20", corner_radius=16)
        top_bar.pack(fill="x", padx=24, pady=(24, 16))
        top_bar.grid_columnconfigure(0, weight=0)
        top_bar.grid_columnconfigure(1, weight=1)
        top_bar.grid_columnconfigure(2, weight=0)
        top_bar.grid_columnconfigure(3, weight=0)

        # --- Scan Entry ---
        scan_icon = self._load_icon("scan.png", size=(28, 28))
        scan_entry_frame = CTkFrame(top_bar, fg_color="transparent")
        scan_entry_frame.grid(row=0, column=0, sticky="w", padx=(0, 12))
        scan_icon_label = CTkLabel(scan_entry_frame, image=scan_icon, text="", width=32)
        scan_icon_label.pack(side="left", padx=(0, 8))
        self.scan_entry = CTkEntry(scan_entry_frame, width=260, height=44, placeholder_text="Scan card ID (press Ctrl+S)", font=("Roboto", 14))
        self.scan_entry.pack(side="left", padx=(0, 0), pady=0)
        self.scan_entry.bind("<Return>", lambda _e: self.scan_on_scan())
        self.pb = CTkProgressBar(scan_entry_frame, mode="indeterminate", width=260)
        self.pb.pack_forget()

        # --- Add Student Button ---
        add_icon = self._load_icon("person_add.png", size=(32, 32))
        self.add_student_button = CTkButton(top_bar, width=44, height=44, text="", image=add_icon, fg_color="#232a36", corner_radius=22, command=self._on_add_student_flow)
        self.add_student_button.grid(row=0, column=1, sticky="w", padx=(0, 12))
        if self.read_only:
            self.scan_entry.configure(state="disabled"); self.scan_entry.unbind("<Return>"); self.add_student_button.grid_remove()

        # --- Search & Filter ---
        search_filter_frame = CTkFrame(top_bar, fg_color="transparent")
        search_filter_frame.grid(row=0, column=2, sticky="ew", padx=(0, 12))
        self.search_var = ctk.StringVar()
        search_icon = self._load_icon("search.png", size=(24, 24))
        search_entry_frame = CTkFrame(search_filter_frame, fg_color="transparent")
        search_entry_frame.pack(side="left", padx=(0, 0))
        search_icon_label = CTkLabel(search_entry_frame, image=search_icon, text="", width=28)
        search_icon_label.pack(side="left", padx=(0, 6))
        search_entry = CTkEntry(search_entry_frame, textvariable=self.search_var, width=220, height=44, placeholder_text="Search by name, ID, card, or phone")
        search_entry.pack(side="left")
        self.search_var.trace_add("write", self._on_search_change)
        self._search_entries.append(search_entry)
        search_entry.bind("<FocusIn>", lambda _e: self._pause_focus_guard())
        search_entry.bind("<FocusOut>", lambda _e: self._resume_focus_guard())
        self.smart_search_entry = search_entry
        filter_icon = self._load_icon("filter.png", size=(28, 28))
        self.filter_button = CTkButton(search_filter_frame, width=44, height=44, text="", image=filter_icon, fg_color="#232a36", corner_radius=22, command=self._on_filter_click)
        self.filter_button.pack(side="left", padx=(8, 0))

        # --- Actions ---
        actions_frame = CTkFrame(top_bar, fg_color="transparent")
        actions_frame.grid(row=0, column=3, sticky="e", padx=(0, 0))
        logout_icon = self._load_icon("logout.png", size=(24, 24))
        self.end_button = CTkButton(
            actions_frame,
            text="End Session" if not self.read_only else "Close",
            command=self._on_end_scan,
            width=120,
            height=44,
            fg_color="#c04040",      # A more prominent red color
            hover_color="#a03030",   # A darker red for hover
            text_color="#ffffff",
            font=("Roboto", 14, "bold"),
            image=logout_icon,
            compound="right"
        )
        self.end_button.pack(side="right", padx=(0, 0))

        # --- Stats strip ---
        self.stats_strip = ScanStatsStrip(
            self,
            load_icon=self._load_icon,
            show_exam=bool(self.restrictions.get("exam") and self.mapping.get("exam", "") in self.df.columns),
            show_homework=bool(self.restrictions.get("homework") and self.mapping.get("homework", "") in self.df.columns),
        )
        self.stats_strip.pack(fill="x", padx=24, pady=(0, 8))

        # --- Main content area with integrated Focus View ---
        main_body = CTkFrame(self, fg_color="transparent")
        main_body.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        main_body.grid_rowconfigure(0, weight=1)
        main_body.grid_columnconfigure(0, weight=1)
        main_body.grid_columnconfigure(1, weight=0) # Focus view column, initially no weight

        # --- Treeview Container (Left/Main) ---
        tree_outer_container = CTkFrame(main_body, fg_color=DARK_SURFACE, corner_radius=18)
        tree_outer_container.grid(row=0, column=0, sticky="nsew")
        tree_outer_container.grid_rowconfigure(0, weight=1)
        tree_outer_container.grid_columnconfigure(0, weight=1)

        tree_container = CTkFrame(tree_outer_container, fg_color="transparent")
        tree_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)
        
        cols = ["card_id", "student_id", "name", "phone"]
        _exam_col = self.mapping.get("exam", "")
        _hw_col = self.mapping.get("homework", "")
        if self.restrictions.get("exam") and _exam_col and _exam_col in self.df.columns:
            cols.append("exam")
        if self.restrictions.get("homework") and _hw_col and _hw_col in self.df.columns:
            cols.append("homework")
        cols += ["attendance", "notes", "timestamp"]

        # Manual column widths
        column_widths = {
            "card_id": 90,
            "student_id": 90,
            "name": 220,
            "phone": 130,
            "exam": 85,
            "homework": 85,
            "attendance": 100,
            "notes": 200,
            "timestamp": 100,
        }

        self.tree = ttk.Treeview(tree_container, columns=cols, show="headings", selectmode="browse")
        self.tree.tag_configure(AUTO_ATTEND_SUCCESS_TAG, background=AUTO_ATTEND_FLASH_BG, foreground=AUTO_ATTEND_FLASH_FG)
        for col in cols:
            width = column_widths.get(col, 110)
            self.tree.heading(col, text=col.replace("_", " ").title())
            if col == "notes":
                # Stretch notes column to fill remaining space and left-align text
                self.tree.column(col, anchor="w", width=width, stretch=True)
            else:
                self.tree.column(col, anchor="center", width=width, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns"); self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self.scan_on_row_double_click)
        if self.read_only: self.tree.unbind("<Double-1>")
        # Bind up/down arrow keys for navigation
        self.tree.bind("<Return>", self._on_tree_enter)
        self.tree.bind("<Up>", self._on_tree_up_down)
        self.tree.bind("<Down>", self._on_tree_up_down)

        # --- Column Sorting ---
        self._tree_sort_column = None
        self._tree_sort_reverse = False
        for col in cols:
            self.tree.heading(col, command=lambda c=col: self._on_treeview_sort(c))

        # --- Focus View Container (Right, initially hidden) ---
        self.focus_view_container = CTkFrame(main_body, fg_color=DARK_SURFACE, corner_radius=18, width=400)
        self.focus_view_container.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        self.focus_view_container.grid_propagate(False) # Prevent resizing
        self.scan_focus_create_ui(self.focus_view_container)
        self.focus_view_container.grid_remove() # Hide it initially

        # Configure column weights for resizing
        main_body.grid_columnconfigure(1, weight=0) # Focus view column

    def _on_treeview_sort(self, col):
        # Get all items and their values for the column
        items = [(iid, self.tree.set(iid, col)) for iid in self._all_iids if self.tree.exists(iid)]
        # Determine if numeric sort (for exam/homework)
        def is_number(val):
            try:
                float(val)
                return True
            except Exception:
                return False
        numeric_cols = {"exam", "homework"}
        # Use str(v).strip() to avoid attribute error
        def parse_score(val):
            val = str(val).strip()
            if not val:
                return float('-inf')  # Treat empty as lowest
            if '/' in val:
                try:
                    score, total = val.split('/', 1)
                    return float(score) / float(total) if float(total) != 0 else float('-inf')
                except Exception:
                    return float('-inf')
            try:
                return float(val)
            except Exception:
                return float('-inf')

        def sort_key(item):
            val = item[1]
            if col in {"exam", "homework"}:
                return parse_score(val)
            else:
                return str(val).lower()
        # Toggle sort order if same column
        if self._tree_sort_column == col:
            self._tree_sort_reverse = not self._tree_sort_reverse
        else:
            self._tree_sort_column = col
            self._tree_sort_reverse = False
        sorted_items = sorted(items, key=sort_key, reverse=self._tree_sort_reverse)
        # Detach all
        for iid in self._all_iids:
            if self.tree.exists(iid):
                self.tree.detach(iid)
        # Re-attach in sorted order
        for iid, _ in sorted_items:
            self.tree.reattach(iid, '', 'end')
    def _on_tree_enter(self, event):
        # Simulate double-click on selected row when Enter is pressed
        selected = self.tree.selection()
        if selected:
            self.scan_on_open_row(selected[0], source="manual")

    def _on_tree_up_down(self, event):
        """Move selection up or down in the Treeview respecting the current visual order."""
        selected_iid = self.tree.selection()

        # Get only the currently visible children in their visual order.
        visible_children = self.tree.get_children('')
        if not visible_children:
            return "break" # Nothing to navigate

        # If nothing is selected, select the first visible item and stop.
        if not selected_iid:
            first_item = visible_children[0]
            self.tree.selection_set(first_item)
            self.tree.focus(first_item)
            self.tree.see(first_item)
            return "break"

        current_iid = selected_iid[0]
        try:
            current_index = visible_children.index(current_iid)
        except ValueError:
            # The selected item is not visible, so select the first visible one
            first_item = visible_children[0]
            self.tree.selection_set(first_item)
            self.tree.focus(first_item)
            self.tree.see(first_item)
            return "break"

        # Determine the next index
        if event.keysym == "Up":
            next_index = current_index - 1
        else:  # Down
            next_index = current_index + 1
            
        # Select the new item if it's within bounds
        if 0 <= next_index < len(visible_children):
            next_item = visible_children[next_index]
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)
        
        # This is crucial: it prevents the default event from firing and causing a "skip".
        return "break"

    def scan_focus_cancel_timer(self):
        if self.scan_focus_timer is not None:
            try: self.after_cancel(self.scan_focus_timer)
            except Exception: pass
            self.scan_focus_timer = None

    def scan_focus_schedule_clear(self, delay=1000):
        self.scan_focus_cancel_timer()
        self.scan_focus_timer = self.after(delay, self.scan_focus_clear)

    def scan_restore_from_focus(self):
        if not self.scan_focus_visible_cache: return
        for scan_iid in self.scan_focus_visible_cache:
            if self.tree.exists(scan_iid):
                try: self.tree.reattach(scan_iid, "", "end")
                except Exception: pass
        self.scan_focus_visible_cache = []

    def scan_filter_for_focus(self, target_iids):
        self.scan_restore_from_focus()
        if not target_iids: return
        current_visible = [iid for iid in self._all_iids if self.tree.exists(iid) and not self.tree.parent(iid)]
        self.scan_focus_visible_cache = current_visible
        for scan_iid in current_visible:
            if scan_iid not in target_iids:
                try: self.tree.detach(scan_iid)
                except Exception: pass
        for scan_iid in target_iids:
            if self.tree.exists(scan_iid):
                try: self.tree.reattach(scan_iid, "", "end")
                except Exception: pass
        primary = target_iids[0]
        if self.tree.exists(primary):
            self.tree.selection_set(primary); self.tree.focus(primary)

    def scan_normalize_card(self, value):
        text = self._clean_value(value)
        return text.zfill(8) if text and text.isdigit() else text

    def scan_lookup_matches(self, card_id):
        normalized = self.scan_normalize_card(card_id)
        if not normalized: return []
        candidates = [iid for iid in self._all_iids if self.tree.exists(iid) and (self.scan_normalize_card(iid) == normalized or self.scan_normalize_card(self.scan_tree_get(iid, "card_id")) == normalized)]
        unique = sorted(list(set(candidates)), key=lambda x: (x != normalized))
        return unique

    def scan_tree_get(self, iid, column):
        if column not in self.tree["columns"]:
            return ""
        try: return self._clean_value(self.tree.set(iid, column))
        except Exception: return ""

    def scan_collect_missing_tasks(self, iid):
        return collect_missing_tasks(self._get_row_values(iid), self.restrictions)

    def scan_describe_tasks(self, tasks):
        return describe_tasks(tasks)

    def scan_append_notes(self, original, addition):
        return append_notes(original, addition)

    def scan_collect_new_note(self, context=None):
        if not hasattr(self, "focus_view") or self.focus_view is None:
            return ""
        if self.focus_view_container and not self.focus_view_container.winfo_ismapped():
            return ""
        ctx = context if context is not None else getattr(self, "scan_focus_ctx", None)
        if not ctx:
            return ""
        try:
            raw_text = self.focus_view.notes.get("1.0", "end-1c")
        except Exception:
            return ""
        if raw_text is None:
            return ""
        raw_text = raw_text.replace("\r\n", "\n")
        candidate = self._clean_value(raw_text)
        if candidate == PLACEHOLDER_TEXT:
            self._notes_placeholder_active = True
            return ""
        self._notes_placeholder_active = False
        if not candidate:
            return ""
        original_raw = (ctx.get("original_notes") or "").replace("\r\n", "\n")
        original_clean = self._clean_value(original_raw)
        if original_clean:
            if candidate == original_clean:
                return ""
            if candidate.startswith(original_clean):
                remainder = candidate[len(original_clean):].lstrip()
                return self._clean_value(remainder)
        return candidate

    def _current_datetime(self):
        return datetime.now()

    def _format_column_timestamp(self, dt):
        return format_column_timestamp(dt)

    def _format_note_tag(self, dt):
        return format_note_tag(dt)

    def scan_now_timestamps(self):
        current_dt = self._current_datetime()
        return self._format_column_timestamp(current_dt), self._format_note_tag(current_dt)

    def scan_now_tag(self):
        _, note_tag = self.scan_now_timestamps()
        return note_tag

    def scan_determine_status(self, scan_ctx):
        return determine_scan_status(scan_ctx)

    def _get_row_values(self, iid):
        return {column: self.scan_tree_get(iid, column) for column in self.tree["columns"]}

    def scan_build_context_for_iid(self, iid, *, source="manual"):
        row = self._get_row_values(iid)
        row["_restrictions"] = self.restrictions
        return build_scan_context(iid, row, source=source, normalized_iid=self.scan_normalize_card(iid))

    def scan_build_not_found_context(self, card_id):
        return {
            "iid": None, "card_id": card_id, "card_display": card_id, "name": "Card Not Linked",
            "student_id": "", "attendance": "", "existing_notes": "", "timestamp": "",
            "source": "scan", "focus_iids": [], "found": False, "missing_tasks": [],
            "status": "not_found", "display_name": card_id or "Card",
        }

    def scan_on_scan(self):
        if self.read_only: return
        self._persist_active_focus_notes()
        normalized = self.scan_normalize_card(self.scan_entry.get())
        self.scan_entry.delete(0, "end")
        if not normalized: return
        
        matches = self.scan_lookup_matches(normalized)
        if not matches:
            context = self.scan_build_not_found_context(normalized)
            self.scan_focus_show(context)
            return
        
        if len(matches) > 1:
            context = {
                "card_id": normalized, "card_display": normalized, "name": "Multiple Records Found",
                "student_id": "", "status": "duplicate", "focus_iids": matches, "skip_filter": True,
            }
            self.scan_focus_show(context)
            return
        
        self.scan_on_open_row(matches[0], source="scan", card_id=normalized)

    def scan_on_row_double_click(self, event):
        if self.read_only: return
        scan_iid = self.tree.identify_row(event.y) or (self.tree.selection() and self.tree.selection()[0])
        if scan_iid: self.scan_on_open_row(scan_iid, source="manual")

    def scan_on_open_row(self, iid, *, source="manual", card_id=None):
        if self.read_only or not self.tree.exists(iid): return
        self._persist_active_focus_notes()
        
        # --- START: MODIFIED LOGIC ---
        context = self.scan_build_context_for_iid(iid, source=source)
        if card_id: context["card_id"] = context["card_display"] = card_id
        
        # If the student has no issues, auto-attend and dismiss.
        # This applies to both scans and manual double-clicks.
        if context["status"] == "ok":
            self.scan_handle_auto_attend(context)
        
        # For all other cases, show the focus view:
        # - If the student has missing tasks (status is not 'ok').
        # - If the student has already attended (status is 'already_attended').
        else:
            self.scan_focus_show(context)
        # --- END: MODIFIED LOGIC ---

    def _notes_have_changed(self):
        """Checks if the notes in the focus view have been modified."""
        if not self.scan_focus_ctx or not self.scan_focus_ctx.get("iid"):
            return False

        new_note_content = self._get_focus_note_content()
        if new_note_content is None:
            return False
        original_notes = self.scan_focus_ctx.get("original_notes", "")
        return self._normalize_note_text(new_note_content) != self._normalize_note_text(original_notes)

    def _normalize_note_text(self, value):
        return ("" if value is None else str(value).strip()).replace("\r\n", "\n")

    def _get_focus_note_content(self):
        if not self.scan_focus_ctx or not self.scan_focus_ctx.get("iid"):
            return None
        try:
            raw_note_content = self.focus_view.notes.get("1.0", "end-1c")
        except Exception:
            return None
        normalized = self._normalize_note_text(raw_note_content)
        if normalized == PLACEHOLDER_TEXT:
            self._notes_placeholder_active = True
            return ""
        self._notes_placeholder_active = False
        return raw_note_content.strip()

    def _sync_focus_note_context(self, notes):
        if not self.scan_focus_ctx:
            return
        clean_notes = self._clean_value(notes)
        self.scan_focus_ctx["existing_notes"] = clean_notes
        self.scan_focus_ctx["original_notes"] = clean_notes

    def _persist_active_focus_notes(self, *, flush=False):
        if not self._is_focus_view_visible():
            return True
        if not self._handle_notes_save():
            return False
        if flush and self.sm.has_pending_changes():
            return self._flush_session_save(show_error=True)
        return True

    def _handle_focus_dismiss_request(self):
        """Handles the request to close the focus view, checking for unsaved notes."""
        if self._notes_have_changed():
            dialog = ConfirmationDialog(
                self,
                title="Unsaved Changes",
                message="You have unsaved changes in the notes. Do you want to save them?",
                confirm_text="Save",
                cancel_text="Dismiss"
            )
            result = dialog.get_result()

            if result is True:  # User clicked "Save"
                if not self._handle_notes_save():
                    return
            elif result is None: # Dialog was closed without a choice
                return # Do nothing, keep the focus view open

        # Dismiss the view if notes were saved, "Dismiss" was clicked, or no changes existed
        self.scan_focus_clear()

    # --- START: NEW SAVE HANDLER METHODS ---

    def _handle_notes_save(self):
        """Called when the notes box loses focus. Saves changes if any were made."""
        if not self.scan_focus_ctx or not self.scan_focus_ctx.get("iid"):
            return True

        iid = self.scan_focus_ctx.get("iid")

        new_note_content = self._get_focus_note_content()
        if new_note_content is None:
            return True
        original_notes = self.scan_focus_ctx.get("original_notes", "")

        if self._normalize_note_text(new_note_content) == self._normalize_note_text(original_notes):
            return True
        
        return self._save_student_notes(iid, new_note_content)

    def _save_student_notes(self, iid, new_notes):
        """Saves only the notes for a student without changing their attendance status."""
        if self.read_only or not self.tree.exists(iid):
            return False

        # Get current attendance and timestamp to preserve them
        current_attendance = self.scan_tree_get(iid, "attendance")
        current_timestamp = self.scan_tree_get(iid, "timestamp")

        # Build the record payload to be saved to the session file
        rec = self._build_record_payload(iid, current_attendance, new_notes, current_timestamp)
        try:
            changed = self.sm.add_record(rec)
        except Exception as exc:
            messagebox.showwarning("Update Failed", f"Could not save notes: {exc}", parent=self)
            return False

        if changed:
            self._schedule_session_save()

        # Update the Treeview UI
        self.tree.set(iid, "notes", self._clean_value(new_notes))

        self._sync_focus_note_context(new_notes)

        # Provide visual feedback to the user and refresh stats
        self.focus_view.show_save_feedback()
        self._refresh_stats()
        return True

    # --- END: NEW SAVE HANDLER METHODS ---

    def scan_handle_auto_attend(self, context):
        if not context:
            return
        column_timestamp, _ = self.scan_now_timestamps()
        final_note = self._clean_value(context.get("existing_notes", ""))
        success = self.scan_commit_attendance(context["iid"], "attend", final_note, timestamp=column_timestamp, action="attend")
        if success:
            self._handle_auto_attend_success(context)

    def _handle_auto_attend_success(self, context):
        iid = context.get("iid")
        self.scan_focus_cancel_timer()
        if self._is_focus_view_visible():
            self.scan_focus_clear()
        else:
            self.scan_focus_ctx = None
        was_selected = bool(iid) and iid in (self.tree.selection() or ())
        if was_selected:
            try:
                self.tree.selection_remove(iid)
            except Exception:
                was_selected = False
        self._flash_tree_row(iid)
        if was_selected:
            def _restore_tree_selection(target=iid):
                if not self.tree.exists(target):
                    return
                if self.tree.selection():
                    return
                try:
                    self.tree.selection_set(target)
                    self.tree.focus(target)
                except Exception:
                    pass
            self.after(AUTO_ATTEND_FLASH_DURATION_MS + 50, _restore_tree_selection)
        self._announce_auto_attend(context)
        self.after(120, self.scan_entry.focus_set)

    def _is_focus_view_visible(self):
        return bool(self.focus_view_container and self.focus_view_container.winfo_ismapped())

    def _flash_tree_row(self, iid, duration=AUTO_ATTEND_FLASH_DURATION_MS):
        if not iid or not self.tree.exists(iid):
            return
        tags = list(self.tree.item(iid, "tags") or ())
        if AUTO_ATTEND_SUCCESS_TAG not in tags:
            tags.append(AUTO_ATTEND_SUCCESS_TAG)
            self.tree.item(iid, tags=tuple(tags))
        if iid in self._row_flash_jobs:
            try:
                self.after_cancel(self._row_flash_jobs[iid])
            except Exception:
                pass
            self._row_flash_jobs.pop(iid, None)
        self._row_flash_jobs[iid] = self.after(duration, lambda item=iid: self._clear_tree_tag(item, AUTO_ATTEND_SUCCESS_TAG))

    def _clear_tree_tag(self, iid, tag_name):
        self._row_flash_jobs.pop(iid, None)
        if not iid or not self.tree.exists(iid):
            return
        remaining = tuple(tag for tag in (self.tree.item(iid, "tags") or ()) if tag != tag_name)
        self.tree.item(iid, tags=remaining)

    def _announce_auto_attend(self, context):
        if not hasattr(self.parent, "set_status"):
            return
        display_name = context.get("display_name") or context.get("name") or context.get("student_id") or context.get("card_display") or "Student"
        message_name = self._clean_value(display_name) or "Student"
        self.parent.set_status(f"{message_name} marked as attended.")

    def _schedule_session_save(self):
        if self.read_only or not self.sm.has_pending_changes():
            return
        if self._pending_session_save_job is not None:
            try:
                self.after_cancel(self._pending_session_save_job)
            except Exception:
                pass
        self._pending_session_save_job = self.after(
            SESSION_SAVE_DEBOUNCE_MS,
            lambda: self._flush_session_save(show_error=True),
        )

    def _flush_session_save(self, *, show_error):
        if self._pending_session_save_job is not None:
            try:
                self.after_cancel(self._pending_session_save_job)
            except Exception:
                pass
            self._pending_session_save_job = None
        if self.read_only or not self.sm.has_pending_changes():
            return True
        try:
            self.sm.save()
        except Exception as exc:
            if show_error:
                messagebox.showwarning("Save Failed", f"Could not save session changes: {exc}", parent=self)
            return False
        return True

    def scan_commit_attendance(self, iid, attendance, notes, *, timestamp=None, warn_on_duplicate=False, action=None):
        try: return bool(self._set_attendance(iid, attendance, notes, warn_on_duplicate=warn_on_duplicate, timestamp_override=timestamp, action=action))
        except Exception as exc: messagebox.showwarning("Attendance Update Failed", str(exc), parent=self); return False # type: ignore

    def _commit_focus_action(self, action_name):
        context = self.scan_focus_ctx or {}
        if not context.get("iid"):
            return
        typed_note = self.scan_collect_new_note(context)
        payload = build_focus_action_payload(action_name, context, typed_note, self._current_datetime())
        if self.scan_commit_attendance(
            context["iid"],
            payload["attendance"],
            payload["final_note"],
            timestamp=payload["column_timestamp"],
            action=payload["record_action"],
        ):
            self.scan_focus_clear()

    def scan_focus_on_completed(self):
        self._commit_focus_action("completed")

    def scan_focus_on_override(self):
        self._commit_focus_action("override")

    def scan_focus_on_deny(self):
        self._commit_focus_action("denied")

    def scan_focus_on_add_student(self):
        if self.read_only: return
        context = self.scan_focus_ctx or {}
        card_id = context.get("card_id") or context.get("card_display")
        typed = self.scan_collect_new_note(context)
        default_notes = build_manual_add_default_notes(context, typed, DIFF_GROUP_NOTE)
        self._launch_add_student_dialog(card_id=card_id, default_notes=default_notes or "")

    def scan_focus_on_cancel_attendance(self):
        self._commit_focus_action("canceled")

    def _apply_treeview_style(self):
        style = ttk.Style(self)
        style.theme_use("default")
        bg, fg, heading_bg, heading_fg = ("#1e1e1e", "#f2f2f2", "#1f6aa5", "#ffffff")
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, rowheight=32, font=("Roboto", 11))
        style.map("Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=heading_bg, foreground=heading_fg, font=("Roboto", 11, "bold") )
        style.map("Treeview.Heading", background=[("active", heading_bg)])
        self.tree.configure(style="Treeview")

    def _load_existing(self):
        def pad_card_id(val):
            val_str = str(val).strip()
            return val_str.zfill(8) if val_str.isdigit() else val_str

        cols = self.tree["columns"]
        session_records = {pad_card_id(rec.get("card_id", "")): rec for rec in self.sm.records}
        self._all_iids = []

        for _, row in self.df.iterrows():
            cid = pad_card_id(row.get(self.mapping.get("card_id", "card_id"), ""))
            rec = session_records.pop(cid, None)
            # REPLACEMENT for the line above
            values = []
            for col in cols:
                val = self._clean_value(rec.get(col) if rec and col in rec else row.get(self.mapping.get(col, col), ""))
                if col == 'name':
                    val = _format_arabic_text(val)
                values.append(val)
            self.tree.insert("", "end", iid=cid, values=tuple(values))
            self._all_iids.append(cid)

        for cid, rec in session_records.items():
            values = [self._clean_value(rec.get(col, "")) for col in cols]
            self.tree.insert("", "end", iid=cid, values=tuple(values))
            self._all_iids.append(cid)

        for iid in self._all_iids:
            self._update_row(iid, self.scan_tree_get(iid, "attendance"), self.scan_tree_get(iid, "notes"), self.scan_tree_get(iid, "timestamp"))

    def _clean_value(self, value):
        if value is None or (isinstance(value, float) and pd.isna(value)): return ""
        text = str(value).strip()
        return "" if text.lower() == "nan" else text

    def _compute_summary_metrics(self):
        total = len(self._all_iids)
        attended = sum(1 for iid in self._all_iids if self.tree.exists(iid) and self.scan_tree_get(iid, "attendance").lower() == "attend")
        metrics = {"total": total, "attended": attended, "attendance_rate": f"{(attended / total) * 100:.1f}%" if total else "0%"}
        if self.restrictions.get("exam") and "exam" in self.tree["columns"]: metrics["missing_exam"] = sum(1 for iid in self._all_iids if self.tree.exists(iid) and grade_missing_or_zero(self.scan_tree_get(iid, "exam")))
        if self.restrictions.get("homework") and "homework" in self.tree["columns"]:
            missing_hw_count = 0
            for iid in self._all_iids:
                if self.tree.exists(iid) and grade_missing_or_zero(self.scan_tree_get(iid, "homework")):
                    missing_hw_count += 1
            metrics["missing_hw"] = missing_hw_count
        return metrics

    def _build_summary_payload(self):
        return compute_session_summary(self.sm.get_dataframe(copy=True), self.mapping, self.restrictions)

    def _refresh_stats(self):
        metrics = self._compute_summary_metrics()
        if self.stats_strip is not None:
            self.stats_strip.update_metrics(metrics)

    def _safe_destroy(self, widget):
        """Safely destroys a widget if it exists."""
        if widget and hasattr(widget, "winfo_exists") and widget.winfo_exists():
            try:
                widget.destroy()
            except Exception:
                pass

    def _finalize_and_close(self, status_message=None):
        if status_message is None: status_message = f"Session '{self.sm.name}' saved and closed."
        if not self._flush_session_save(show_error=True):
            return
        summary, session_name, session_path, parent, read_only = self._build_summary_payload(), self.sm.name, getattr(self.sm, "session_path", None), self.parent, getattr(self, "read_only", False)
        
        # Safely destroy the main scan window
        self._safe_destroy(self)
        
        if hasattr(parent, "_refresh_recent_sessions"): parent._refresh_recent_sessions()
        if hasattr(parent, "set_status"): parent.set_status(status_message)
        if hasattr(parent, "show_session_summary"):
            parent.after(160, lambda: parent.show_session_summary(session_name=session_name, summary=summary, session_path=session_path, read_only=read_only))

    def _on_search_change(self, *_): self._filter_all()

    def _filter_all(self):
        query = self._clean_value(self.search_var.get()).lower() if self.search_var else ""
        terms = [term for term in query.split() if term]
        filters = {
            "attendance": self._filter_vars["attendance"].get(),
            "missing_exam": self._filter_vars["missing_exam"].get(),
            "missing_hw": self._filter_vars["missing_hw"].get(),
            "has_exam": self._filter_vars["has_exam"].get(),
            "has_hw": self._filter_vars["has_hw"].get(),
            "has_notes": self._filter_vars["has_notes"].get(),
            "manual_added": self._filter_vars["manual_added"].get(),
        }

        for iid in self._all_iids:
            if not self.tree.exists(iid): continue
            row = self._get_row_values(iid)
            show = row_matches_filters(row, iid, terms, filters, self.restrictions)
            if show:
                self.tree.reattach(iid, '', 'end')
            else:
                self.tree.detach(iid)

    def _set_attendance(self, code, attendance, notes, *, warn_on_duplicate=True, timestamp_override=None, action=None):
        if self.read_only or not self.tree.exists(code):
            return False
        current_dt = self._current_datetime()
        row = self._get_row_values(code)
        rec, column_timestamp, is_first_attend = prepare_attendance_update(
            row,
            code,
            attendance,
            notes,
            current_dt,
            timestamp_override=timestamp_override,
            action=action,
        )
        try:
            changed = self.sm.add_record(rec)
        except Exception as exc:
            messagebox.showwarning("Attendance Update Failed", str(exc), parent=self); return False # type: ignore
        if changed:
            self._schedule_session_save()
        if is_first_attend:
            self._update_row(code, rec["attendance"], rec["notes"], column_timestamp)
        else:
            self._update_row(code, rec["attendance"], rec["notes"])
        self._refresh_stats()
        return True

    def _build_record_payload(self, code, attendance, notes, timestamp):
        row = self._get_row_values(code)
        return build_record_payload(row, code, attendance, notes, timestamp)

    def _update_row(self, code, attendance, notes, timestamp=None):
        if not self.tree.exists(code): return
        try:
            self.tree.set(code, "attendance", self._clean_value(attendance))
            self.tree.set(code, "notes", self._clean_value(notes))
            if timestamp is not None: self.tree.set(code, "timestamp", self._clean_value(timestamp))
        except Exception: pass

    def _on_add_student_flow(self): self._launch_add_student_dialog()

    def _launch_add_student_dialog(self, card_id=None, default_notes="Manually added"):
        if self.read_only: return
        self._pause_focus_guard()
        normalized_card = None
        if card_id:
            raw_card = str(card_id).strip()
            normalized_card = raw_card.zfill(8) if raw_card.isdigit() else raw_card
        
        dialog = AddStudentDialog(self, card_id=normalized_card, duplicate_checker=self._student_id_or_phone_exists, default_notes=default_notes, on_submit=self._handle_add_student_submission)
        dialog.bind("<Destroy>", lambda e: self._resume_focus_guard(), add="+")

    def _handle_add_student_submission(self, *, card_id, values, default_notes):
        cid = str(card_id).strip() if card_id else self._next_unknown_card_id()
        if cid.isdigit(): cid = cid.zfill(8)
        
        current_dt = self._current_datetime()
        rec = build_manual_add_record(cid, values, default_notes, current_dt, self.restrictions)
        
        try: changed = self.sm.add_record(rec)
        except Exception as exc: messagebox.showwarning("Unable to add student", str(exc), parent=self); return False

        if changed:
            self._schedule_session_save()

        row_values = [rec.get(col, "") for col in self.tree["columns"]]
        
        if self.tree.exists(cid): self.tree.item(cid, values=tuple(row_values))
        else: self.tree.insert("", "end", iid=cid, values=tuple(row_values)); self._all_iids.append(cid)
        
        self._refresh_stats()
        
        if self.scan_focus_ctx and self.scan_focus_ctx.get("status") == "not_found":
            self.scan_focus_clear()
        
        self.after(120, self.scan_entry.focus_set)
        return True

    def _next_unknown_card_id(self):
        if not hasattr(self, "_unknown_counter"):
            existing = [int(r.get("card_id", "").split("Unknown ")[-1]) for r in self.sm.records if str(r.get("card_id", "")).startswith("Unknown ")]
            self._unknown_counter = max(existing, default=0)
        self._unknown_counter += 1
        return f"Unknown {self._unknown_counter}"

    def _on_end_scan(self):
        if not self._persist_active_focus_notes(flush=True):
            return
        msg = f"Session '{self.sm.name}' closed (view-only)." if self.read_only else None
        self._finalize_and_close(status_message=msg)

    def _global_focus_in(self, _event):
         if self._focus_reset_job is not None:
             self.after_cancel(self._focus_reset_job); self._focus_reset_job = None
         if self.read_only or self._focus_guard_depth > 0: return
         
         widget = self.focus_get()
         if widget is None or widget.winfo_toplevel() is not self: return
         
         # FIX 1: Explicitly ignore the Treeview widget itself
         if widget is self.tree: return
 
         # This check is still valid for the scan and search entries
         if widget in {self.scan_entry, *self._search_entries}: return
 
         # FIX 2: Check against the correct Focus View container
         parent = getattr(widget, "master", None)
         while parent is not None:
             # Check if the focused widget is a child of the integrated focus view
             if parent == getattr(self, "focus_view_container", None): return
             parent = getattr(parent, "master", None)
             
         self._focus_reset_job = self.after_idle(self._focus_scan_entry)

    def _student_id_or_phone_exists(self, student_id, phone):
        return self.sm.has_student_id_or_phone(student_id, phone)
