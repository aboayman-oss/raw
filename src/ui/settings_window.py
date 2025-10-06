"""Settings window for configuring application preferences."""
import json
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk
from customtkinter import (
    CTkButton,
    CTkComboBox,
    CTkEntry,
    CTkFrame,
    CTkImage,
    CTkLabel,
    CTkScrollableFrame,
    CTkSegmentedButton,
    CTkSwitch,
    CTkTabview,
    CTkToplevel,
)
from PIL import Image

from utils.helpers import (
    FOLDER_OPEN_ICON_FILE,
    MAPPING_FILE,
    MIN_SETTINGS_SIZE,
    PLUS_ICON_FILE,
    REMOVE_ICON_FILE,
    SETTINGS,
    SETTINGS_FILE,
    STATUS_INFO_ICON_FILE,
    STATUS_OK_ICON_FILE,
    bring_window_to_front,
    ensure_initial_size,
    read_data,
    set_dark_title_bar,
)


class SettingsWindow(CTkToplevel):
    """Toplevel dialog for managing template mapping, stage lists, and preferences."""

    mapping_placeholder = "-- Select --"
    _list_row_base_color = "#454545"
    _list_row_hover_color = "#515151"

    def __init__(self, parent):
        super().__init__(parent)
        set_dark_title_bar(self)
        self.title("Settings")
        self.minsize(*MIN_SETTINGS_SIZE)
        self.configure(fg_color="#2B2B2B")

        self.parent_app = parent
        self.after(50, lambda: bring_window_to_front(self))

        self.column_map = dict(getattr(parent, "column_map", {}) or {})
        self.working_mapping = dict(self.column_map)
        self.mapping_fields = [
            ("Card ID", "card_id"),
            ("Student ID", "student_id"),
            ("Name", "name"),
            ("Phone no.", "phone"),
            ("Attendance", "attendance"),
            ("Notes", "notes"),
            ("Timestamp", "timestamp"),
            ("Exam", "exam"),
            ("Homework", "homework"),
        ]
        self.mapping_labels = {field_key: label_text for label_text, field_key in self.mapping_fields}
        self.mapping_controls = {}
        self.mapping_hint_labels = {}
        self.mapping_source_path = None
        self.mapping_columns = []
        for value in self.working_mapping.values():
            if value and value not in self.mapping_columns:
                self.mapping_columns.append(value)

        self.stage_items = list(SETTINGS["stage_options"])
        self.center_items = list(SETTINGS["center_options"])
        self.stage_rows = {}
        self.center_rows = {}

        self.var_exam = ctk.BooleanVar(value=SETTINGS["restrictions"].get("exam", False))
        self.var_homework = ctk.BooleanVar(value=SETTINGS["restrictions"].get("homework", False))
        self.var_file_type = ctk.StringVar(value=SETTINGS.get("file_type", "xlsx").upper())

        self.template_status_var = ctk.StringVar()
        self.hint_font = ctk.CTkFont(size=12)

        self._icon_cache = {}
        self.status_icons = {
            "ok": self._load_icon(STATUS_OK_ICON_FILE, (20, 20)),
            "info": self._load_icon(STATUS_INFO_ICON_FILE, (20, 20)),
        }
        self.folder_icon = self._load_icon(FOLDER_OPEN_ICON_FILE, (18, 18))
        self.plus_icon = self._load_icon(PLUS_ICON_FILE, (16, 16))
        self.remove_icon = self._load_icon(REMOVE_ICON_FILE, (14, 14))

        container = CTkFrame(self, fg_color="#2B2B2B")
        container.pack(fill="both", expand=True, padx=32, pady=(20, 36))

        self.tabview = CTkTabview(container, fg_color="#2B2B2B")
        self.tabview.pack(fill="both", expand=True)
        segmented = self.tabview._segmented_button
        segmented.configure(
            fg_color="#2F2F2F",
            selected_color="#2F80ED",
            selected_hover_color="#1C64D1",
            unselected_color="#3C3C3C",
            unselected_hover_color="#454545",
            text_color="#E6E6E6",
        )

        self.template_tab = self.tabview.add("Template Mapping")
        self.stage_tab = self.tabview.add("Stage & Center")
        self.restrictions_tab = self.tabview.add("Restrictions")
        self.filetype_tab = self.tabview.add("File Type")

        self._build_template_tab()
        self._build_stage_tab()
        self._build_restrictions_tab()
        self._build_filetype_tab()

        btn_frame = CTkFrame(self, fg_color="#2F2F2F", corner_radius=12)
        btn_frame.pack(side="bottom", fill="x", padx=32, pady=(8, 20))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.cancel_button = CTkButton(
            btn_frame,
            text="Cancel",
            command=self._cancel,
            fg_color="#2B2B2B",
            hover_color="#34445F",
            border_width=2,
            border_color="#2F80ED",
            text_color="#2F80ED",
        )
        self.cancel_button.grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=12)

        self.apply_button = CTkButton(
            btn_frame,
            text="Apply",
            command=self._apply_settings,
            fg_color="#2F80ED",
            hover_color="#1C64D1",
            text_color="#FFFFFF",
            state="disabled",
        )
        self.apply_button.grid(row=0, column=1, sticky="ew", padx=(8, 16), pady=12)

        self.action_divider = CTkFrame(self, height=1, fg_color="#3A3A3A")
        self.action_divider.pack(side="bottom", fill="x", padx=32)

        if self.working_mapping:
            self.template_status_var.set("Using saved mapping. Load a sample file to update it.")
        else:
            self.template_status_var.set("Load a sample file to map template fields.")

        self._populate_template_controls()
        self._update_apply_state()
        ensure_initial_size(self, min_size=MIN_SETTINGS_SIZE)

    def _load_icon(self, path, size):
        if not path or not os.path.exists(path):
            return None
        key = (path, size)
        icon = self._icon_cache.get(key)
        if icon is None:
            image = Image.open(path)
            icon = CTkImage(light_image=image, dark_image=image, size=size)
            self._icon_cache[key] = icon
        return icon

    def _build_template_tab(self):
        card = CTkFrame(self.template_tab, fg_color="#3C3C3C", corner_radius=12)
        card.pack(fill="both", expand=True, padx=4, pady=(6, 10))
        card.grid_columnconfigure(0, weight=1)

        CTkLabel(
            card,
            text="Assign each template field to a column from a sample data file.",
            justify="left",
            wraplength=520,
        ).pack(anchor="w", padx=24, pady=(16, 8))

        status_row = CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=24, pady=(0, 8))
        status_row.grid_columnconfigure(0, weight=1)

        status_container = CTkFrame(status_row, fg_color="transparent")
        status_container.grid(row=0, column=0, sticky="w")

        info_icon = self.status_icons.get("info")
        self.template_status_icon_label = CTkLabel(status_container, text="", image=info_icon)
        self.template_status_icon_label.pack(side="left", pady=2)
        if info_icon:
            self.template_status_icon_label.image = info_icon

        CTkLabel(
            status_container,
            textvariable=self.template_status_var,
            justify="left",
            wraplength=420,
        ).pack(side="left", padx=12)

        CTkButton(
            status_row,
            text="Load Source File",
            image=self.folder_icon,
            compound="left",
            command=self._prompt_for_columns,
        ).grid(row=0, column=1, sticky="e")

        form = CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        form.grid_columnconfigure(0, weight=0)
        form.grid_columnconfigure(1, weight=1)
        self.template_form = form

        for idx, (label_text, field_key) in enumerate(self.mapping_fields):
            row = idx * 2
            CTkLabel(form, text=f"{label_text}:").grid(
                row=row,
                column=0,
                sticky="w",
                padx=(0, 18),
                pady=(0, 4),
            )
            combo = CTkComboBox(
                form,
                state="readonly",
                values=[self.mapping_placeholder],
                border_width=1,
                border_color="#2B2B2B",
            )
            combo.grid(row=row, column=1, sticky="ew", pady=(0, 4))
            combo.set(self.mapping_placeholder)
            combo.configure(command=lambda value, key=field_key: self._on_mapping_change(key, value))
            self.mapping_controls[field_key] = combo

            hint = CTkLabel(
                form,
                text="",
                font=self.hint_font,
                text_color="#F28D35",
                justify="left",
                wraplength=420,
            )
            hint.grid(row=row + 1, column=1, sticky="w", pady=(0, 8))
            self.mapping_hint_labels[field_key] = hint

    def _build_stage_tab(self):
        card = CTkFrame(self.stage_tab, fg_color="#3C3C3C", corner_radius=12)
        card.pack(fill="both", expand=True, padx=4, pady=(6, 10))

        CTkLabel(
            card,
            text="Manage the stage and center choices available when starting a session.",
            justify="left",
            wraplength=520,
        ).pack(anchor="w", padx=24, pady=(16, 8))

        lists_frame = CTkFrame(card, fg_color="transparent")
        lists_frame.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        lists_frame.grid_columnconfigure(0, weight=1)
        lists_frame.grid_columnconfigure(1, weight=1)

        stage_column = CTkFrame(lists_frame, fg_color="transparent")
        stage_column.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        stage_column.grid_rowconfigure(1, weight=1)

        CTkLabel(stage_column, text="Stage Options", anchor="w").pack(anchor="w")

        stage_list_card = CTkFrame(stage_column, fg_color="#2F2F2F", corner_radius=12)
        stage_list_card.pack(fill="both", expand=True, pady=(6, 10))
        self.stage_scroll = CTkScrollableFrame(stage_list_card, fg_color="#2F2F2F")
        self.stage_scroll.pack(fill="both", expand=True, padx=8, pady=8)
        self.stage_scroll.grid_columnconfigure(0, weight=1)

        stage_entry_row = CTkFrame(stage_column, fg_color="transparent")
        stage_entry_row.pack(fill="x")
        stage_entry_row.grid_columnconfigure(0, weight=1)

        self.stage_entry = CTkEntry(stage_entry_row, placeholder_text="Add stage")
        self.stage_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.stage_entry.bind("<Return>", lambda _event: self._add_stage())

        CTkButton(
            stage_entry_row,
            text="Add",
            image=self.plus_icon,
            compound="left",
            width=110,
            command=self._add_stage,
        ).grid(row=0, column=1, sticky="e")

        center_column = CTkFrame(lists_frame, fg_color="transparent")
        center_column.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        center_column.grid_rowconfigure(1, weight=1)

        CTkLabel(center_column, text="Center Options", anchor="w").pack(anchor="w")

        center_list_card = CTkFrame(center_column, fg_color="#2F2F2F", corner_radius=12)
        center_list_card.pack(fill="both", expand=True, pady=(6, 10))
        self.center_scroll = CTkScrollableFrame(center_list_card, fg_color="#2F2F2F")
        self.center_scroll.pack(fill="both", expand=True, padx=8, pady=8)
        self.center_scroll.grid_columnconfigure(0, weight=1)

        center_entry_row = CTkFrame(center_column, fg_color="transparent")
        center_entry_row.pack(fill="x")
        center_entry_row.grid_columnconfigure(0, weight=1)

        self.center_entry = CTkEntry(center_entry_row, placeholder_text="Add center")
        self.center_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.center_entry.bind("<Return>", lambda _event: self._add_center())

        CTkButton(
            center_entry_row,
            text="Add",
            image=self.plus_icon,
            compound="left",
            width=110,
            command=self._add_center,
        ).grid(row=0, column=1, sticky="e")

        self._populate_option_rows(self.stage_scroll, self.stage_rows, self.stage_items, self._remove_stage_value)
        self._populate_option_rows(self.center_scroll, self.center_rows, self.center_items, self._remove_center_value)

    def _build_restrictions_tab(self):
        card = CTkFrame(self.restrictions_tab, fg_color="#3C3C3C", corner_radius=12)
        card.pack(fill="both", expand=True, padx=4, pady=(6, 10))
        card.grid_columnconfigure(0, weight=1)

        CTkLabel(
            card,
            text="Toggle optional columns that should be collected during scans.",
            justify="left",
            wraplength=520,
        ).pack(anchor="w", padx=24, pady=(16, 8))

        toggle_card = CTkFrame(card, fg_color="#2F2F2F", corner_radius=12)
        toggle_card.pack(fill="x", padx=24, pady=(0, 16))

        self._add_toggle_row(
            toggle_card,
            title="Enable Exam Column",
            description="Collect exam grades alongside attendance so exports stay complete.",
            variable=self.var_exam,
            bottom_padding=10,
        )
        self._add_toggle_row(
            toggle_card,
            title="Enable Homework Column",
            description="Track homework completion in the same sheet when exporting data.",
            variable=self.var_homework,
            bottom_padding=12,
        )

    def _add_toggle_row(self, parent, *, title, description, variable, bottom_padding):
        row = CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(12, 0))
        row.grid_columnconfigure(0, weight=1)

        CTkLabel(
            row,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        CTkSwitch(
            row,
            text="",
            variable=variable,
            command=self._update_apply_state,
            progress_color="#2F80ED",
            fg_color="#4C4C4C",
            button_color="#FFFFFF",
            button_hover_color="#E0E0E0",
        ).grid(row=0, column=1, sticky="e")

        CTkLabel(
            parent,
            text=description,
            justify="left",
            text_color="#BEBEBE",
            wraplength=520,
        ).pack(fill="x", padx=24, pady=(2, bottom_padding))

    def _build_filetype_tab(self):
        card = CTkFrame(self.filetype_tab, fg_color="#3C3C3C", corner_radius=12)
        card.pack(fill="both", expand=True, padx=4, pady=(6, 10))
        card.grid_columnconfigure(0, weight=1)

        CTkLabel(
            card,
            text="Choose the preferred format when importing or exporting data.",
            justify="left",
            wraplength=520,
        ).pack(anchor="w", padx=24, pady=(16, 8))

        segment_card = CTkFrame(card, fg_color="#2F2F2F", corner_radius=12)
        segment_card.pack(fill="x", padx=24, pady=(0, 16))
        segment_card.grid_columnconfigure(0, weight=1)

        self.filetype_segment = CTkSegmentedButton(
            segment_card,
            values=["CSV", "XLSX"],
            variable=self.var_file_type,
            command=self._on_file_type_change,
        )
        self.filetype_segment.grid(row=0, column=0, padx=16, pady=12, sticky="ew")
        self.filetype_segment.configure(
            fg_color="#2F2F2F",
            selected_color="#2F80ED",
            selected_hover_color="#1C64D1",
            unselected_color="#3C3C3C",
            unselected_hover_color="#454545",
            text_color="#E6E6E6",
        )
        self.filetype_segment.set(self.var_file_type.get())

    def _populate_option_rows(self, container, rows_dict, items, remove_callback):
        for child in container.winfo_children():
            child.destroy()
        rows_dict.clear()
        for value in items:
            self._create_option_row(container, rows_dict, value, remove_callback, animate=False)

    def _create_option_row(self, container, rows_dict, value, remove_callback, animate=False):
        row = CTkFrame(container, fg_color=self._list_row_base_color, corner_radius=10)
        row.pack(fill="x", pady=(0, 8))
        row.grid_columnconfigure(0, weight=1)
        row._hide_job = None  # type: ignore[attr-defined]

        CTkLabel(row, text=value, anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=12)

        button = CTkButton(
            row,
            text="",
            image=self.remove_icon,
            width=36,
            command=lambda: remove_callback(value),
            fg_color="transparent",
            hover_color="#5A5A5A",
        )
        button.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=8)
        button.grid_remove()

        self._bind_row_hover(row, button)
        rows_dict[value] = row

        if animate:
            self._animate_row_in(row)
        else:
            row.configure(fg_color=self._list_row_base_color)
        return row

    def _bind_row_hover(self, row, button):
        widgets = [row, button, *row.winfo_children()]

        def show(_event=None):
            if not row.winfo_exists():
                return
            hide_job = getattr(row, "_hide_job", None)
            if hide_job:
                row.after_cancel(hide_job)
                row._hide_job = None  # type: ignore[attr-defined]
            if not button.winfo_ismapped():
                button.grid()
            row.configure(fg_color=self._list_row_hover_color)

        def schedule_hide(_event=None):
            if not row.winfo_exists():
                return

            def _hide():
                if not row.winfo_exists():
                    return
                pointer_widget = row.winfo_containing(*row.winfo_pointerxy())
                if not self._is_descendant(pointer_widget, row):
                    if button.winfo_exists():
                        button.grid_remove()
                    row.configure(fg_color=self._list_row_base_color)
                row._hide_job = None  # type: ignore[attr-defined]

            hide_job = getattr(row, "_hide_job", None)
            if hide_job:
                row.after_cancel(hide_job)
            row._hide_job = row.after(120, _hide)  # type: ignore[attr-defined]

        for widget in widgets:
            widget.bind("<Enter>", show, add="+")
            widget.bind("<Leave>", schedule_hide, add="+")
        button.bind("<ButtonRelease-1>", lambda _event: schedule_hide(), add="+")

    def _animate_row_in(self, row):
        colors = ["#2F2F2F", "#3C3C3C", self._list_row_base_color]

        def step(index=0):
            if not row.winfo_exists() or index >= len(colors):
                return
            row.configure(fg_color=colors[index])
            if index < len(colors) - 1:
                row.after(60, lambda: step(index + 1))

        step()

    def _is_descendant(self, widget, ancestor):
        while widget is not None:
            if widget is ancestor:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _flash_existing_row(self, row):
        if not row or not row.winfo_exists():
            return

        base = self._list_row_base_color
        accent = "#5C4D4D"

        def pulse(iteration=0):
            if not row.winfo_exists():
                return
            row.configure(fg_color=accent if iteration % 2 == 0 else base)
            if iteration < 3:
                row.after(120, lambda: pulse(iteration + 1))
            else:
                row.configure(fg_color=base)

        pulse()

    def _add_stage(self):
        value = self.stage_entry.get().strip()
        if not value:
            return
        if value in self.stage_items:
            self._flash_existing_row(self.stage_rows.get(value))
            self.stage_entry.delete(0, "end")
            return
        self.stage_items.append(value)
        self._create_option_row(self.stage_scroll, self.stage_rows, value, self._remove_stage_value, animate=True)
        self.stage_entry.delete(0, "end")

    def _remove_stage_value(self, value):
        if value not in self.stage_items:
            return
        self.stage_items.remove(value)
        row = self.stage_rows.pop(value, None)
        if row and row.winfo_exists():
            row.destroy()

    def _add_center(self):
        value = self.center_entry.get().strip()
        if not value:
            return
        if value in self.center_items:
            self._flash_existing_row(self.center_rows.get(value))
            self.center_entry.delete(0, "end")
            return
        self.center_items.append(value)
        self._create_option_row(self.center_scroll, self.center_rows, value, self._remove_center_value, animate=True)
        self.center_entry.delete(0, "end")

    def _remove_center_value(self, value):
        if value not in self.center_items:
            return
        self.center_items.remove(value)
        row = self.center_rows.pop(value, None)
        if row and row.winfo_exists():
            row.destroy()

    def _populate_template_controls(self):
        available = []
        for col in self.mapping_columns:
            col = str(col).strip()
            if col and col not in available:
                available.append(col)
        values = [self.mapping_placeholder] + available if available else [self.mapping_placeholder]

        for field_key, combo in self.mapping_controls.items():
            combo.configure(values=values)
            current = self.working_mapping.get(field_key, "")
            if current and current in available:
                combo.set(current)
            else:
                combo.set(self.mapping_placeholder)
                self.working_mapping[field_key] = ""
        self._refresh_mapping_hints()

    def _on_mapping_change(self, field_key, value):
        cleaned = "" if value in ("", self.mapping_placeholder) else value.strip()
        self.working_mapping[field_key] = cleaned
        self._update_apply_state()

    def _prompt_for_columns(self):
        file_type = self.var_file_type.get().lower()
        ext = "*.xlsx" if file_type == "xlsx" else "*.csv"
        path = filedialog.askopenfilename(
            parent=self,
            title=f"Select {file_type.upper()}",
            filetypes=[(f"{file_type.upper()} files", ext)],
        )
        if not path:
            return
        try:
            df = read_data(path, nrows=0)
        except Exception as exc:
            messagebox.showerror("Load Failed", str(exc), parent=self)
            return
        columns = [str(col).strip() for col in df.columns]
        self.mapping_columns = [col for col in columns if col]
        self.mapping_source_path = path
        self.template_status_var.set(f"Columns loaded from {os.path.basename(path)}.")
        self._populate_template_controls()
        self._update_apply_state()

    def _collect_mapping(self):
        mapping = {}
        for _, field_key in self.mapping_fields:
            value = self.mapping_controls[field_key].get().strip()
            if value == self.mapping_placeholder:
                value = ""
            mapping[field_key] = value
        return mapping

    def _is_mapping_valid(self):
        mapping = self._collect_mapping()
        values = [value for value in mapping.values() if value]
        if len(values) != len(self.mapping_fields):
            return False
        return len(values) == len(set(values))

    def _refresh_mapping_hints(self):
        mapping = self._collect_mapping()
        value_to_fields = {}
        for field_key, column in mapping.items():
            if column:
                value_to_fields.setdefault(column, []).append(field_key)

        conflicts = {
            field
            for columns in value_to_fields.values()
            if len(columns) > 1
            for field in columns
        }

        for field_key, hint_label in self.mapping_hint_labels.items():
            combo = self.mapping_controls[field_key]
            current_value = mapping.get(field_key, "")
            if current_value and field_key in conflicts:
                others = [
                    self.mapping_labels[other]
                    for other in value_to_fields.get(current_value, [])
                    if other != field_key
                ]
                if not others:
                    others = [
                        self.mapping_labels[other]
                        for other in value_to_fields.get(current_value, [])
                    ]
                hint_label.configure(
                    text=f"Already used by {', '.join(others)}." if others else "Duplicate selection.",
                    text_color="#F28D35",
                )
                combo.configure(border_color="#F28D35", border_width=2)
            else:
                hint_label.configure(text="")
                combo.configure(border_color="#2B2B2B", border_width=1)

    def _update_template_status_display(self, is_valid=None):
        if is_valid is None:
            is_valid = self._is_mapping_valid()
        icon_key = "ok" if is_valid else "info"
        if not self.mapping_columns:
            icon_key = "info"
        icon = self.status_icons.get(icon_key)
        if icon:
            self.template_status_icon_label.configure(image=icon)
            self.template_status_icon_label.image = icon

    def _update_apply_state(self):
        self._refresh_mapping_hints()
        is_valid = self._is_mapping_valid()
        self.apply_button.configure(state="normal" if is_valid else "disabled")
        self._update_template_status_display(is_valid)

    def _on_file_type_change(self, value):
        self.var_file_type.set(value)
        self._update_apply_state()

    def _apply_settings(self):
        if not self._is_mapping_valid():
            messagebox.showerror("Invalid Mapping", "Each template field must map to a unique column.", parent=self)
            return

        mapping = self._collect_mapping()
        stage_options = list(self.stage_items)
        center_options = list(self.center_items)
        restrictions = {
            "exam": bool(self.var_exam.get()),
            "homework": bool(self.var_homework.get()),
        }
        file_type = self.var_file_type.get().lower()

        try:
            with open(MAPPING_FILE, "w", encoding="utf-8") as file:
                json.dump(mapping, file, indent=2)
            SETTINGS["stage_options"] = stage_options
            SETTINGS["center_options"] = center_options
            SETTINGS["restrictions"].update(restrictions)
            SETTINGS["file_type"] = file_type
            with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
                json.dump(SETTINGS, file, indent=2)
        except OSError as exc:
            messagebox.showerror("Save Failed", str(exc), parent=self)
            return

        self.parent_app.column_map = mapping
        self.column_map = dict(mapping)
        self.working_mapping = dict(mapping)
        self.mapping_columns = [value for value in mapping.values() if value]

        if hasattr(self.parent_app, "set_status"):
            self.parent_app.set_status("Settings saved.")
        messagebox.showinfo("Settings", "Settings saved successfully.", parent=self)
        self.on_close()

    def _cancel(self):
        if hasattr(self.parent_app, "set_status"):
            self.parent_app.set_status("Settings closed without saving.")
        self.on_close()

    def on_close(self):
        if getattr(self.parent_app, "settings_window", None) is self:
            self.parent_app.settings_window = None
        self.destroy()

