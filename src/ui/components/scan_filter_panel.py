"""Reusable filter panel for the scan window."""

import customtkinter as ctk
from customtkinter import CTkButton, CTkFrame, CTkLabel


class ScanFilterPanel(CTkFrame):
    def __init__(
        self,
        master,
        *,
        filter_vars,
        load_icon,
        on_hide,
        on_filter_change,
        on_task_filter_change,
        on_clear_filters,
        panel_width=320,
    ):
        super().__init__(master, fg_color="#232a36", corner_radius=12, width=panel_width)
        self.filter_vars = filter_vars
        self._load_icon = load_icon
        self._on_hide = on_hide
        self._on_filter_change = on_filter_change
        self._on_task_filter_change = on_task_filter_change
        self._on_clear_filters = on_clear_filters
        self._build()

    def _build(self):
        top_bar = CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=0, pady=(0, 0))
        CTkLabel(top_bar, text="Filters", font=("Roboto", 14, "bold"), anchor="w").pack(side="left", padx=(12, 0), pady=(10, 0))
        x_icon = self._load_icon("close.png", size=(20, 20))
        dismiss_btn = CTkButton(top_bar, text="", image=x_icon, width=32, height=32, fg_color="transparent", command=self._on_hide)
        dismiss_btn.pack(side="right", padx=(0, 8), pady=(10, 0))

        CTkLabel(self, text="Attendance Status", font=("Arial", 12, "bold"), anchor="w").pack(anchor="w", padx=12, pady=(10, 0))
        att_frame = CTkFrame(self, fg_color="transparent")
        att_frame.pack(anchor="w", padx=12, pady=(0, 4))
        for val, label in (("all", "All Students"), ("attend", "Attended"), ("absent", "Absent")):
            ctk.CTkRadioButton(att_frame, text=label, variable=self.filter_vars["attendance"], value=val, command=self._on_filter_change).pack(side="left", padx=(0, 12))

        CTkLabel(self, text="Task Status", font=("Roboto", 12, "bold"), anchor="w").pack(anchor="w", padx=12, pady=(6, 0))
        task_frame = CTkFrame(self, fg_color="transparent")
        task_frame.pack(fill="x", padx=12, pady=(0, 4))
        task_frame.grid_columnconfigure((0, 1), weight=1)

        exam_col_frame = CTkFrame(task_frame, fg_color="transparent")
        exam_col_frame.grid(row=0, column=0, sticky="nsew")
        ctk.CTkCheckBox(
            exam_col_frame,
            text="Missing Exam",
            variable=self.filter_vars["missing_exam"],
            command=lambda: self._on_task_filter_change("exam", "missing"),
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkCheckBox(
            exam_col_frame,
            text="Complete Exam",
            variable=self.filter_vars["has_exam"],
            command=lambda: self._on_task_filter_change("exam", "has"),
        ).pack(anchor="w")

        hw_col_frame = CTkFrame(task_frame, fg_color="transparent")
        hw_col_frame.grid(row=0, column=1, sticky="nsew")
        ctk.CTkCheckBox(
            hw_col_frame,
            text="Missing H.W.",
            variable=self.filter_vars["missing_hw"],
            command=lambda: self._on_task_filter_change("hw", "missing"),
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkCheckBox(
            hw_col_frame,
            text="Complete H.W",
            variable=self.filter_vars["has_hw"],
            command=lambda: self._on_task_filter_change("hw", "has"),
        ).pack(anchor="w")

        CTkLabel(self, text="Other Criteria", font=("Roboto", 12, "bold"), anchor="w").pack(anchor="w", padx=12, pady=(0, 4))
        other_frame = CTkFrame(self, fg_color="transparent")
        other_frame.pack(anchor="w", padx=12, pady=(0, 4))
        ctk.CTkCheckBox(other_frame, text="Has Notes", variable=self.filter_vars["has_notes"], command=self._on_filter_change).pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(other_frame, text="Manually Added (No Card ID)", variable=self.filter_vars["manual_added"], command=self._on_filter_change).pack(side="left", padx=(0, 12))

        clear_btn = CTkButton(self, text="Clear Filters", fg_color="#232a36", command=self._on_clear_filters)
        clear_btn.pack(fill="x", padx=12, pady=(10, 10))