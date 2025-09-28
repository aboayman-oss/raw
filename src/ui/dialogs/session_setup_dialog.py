"""Dialog for configuring basic session metadata."""
import customtkinter as ctk
from customtkinter import CTkButton, CTkComboBox, CTkEntry, CTkFrame, CTkLabel, CTkToplevel

from utils.helpers import MIN_SESSION_SETUP_SIZE, bring_window_to_front, ensure_initial_size


class SessionSetupDialog(CTkToplevel):
    def __init__(self, parent, stages, centers, has_data, callback):
        super().__init__(parent)
        self.parent = parent
        self.placeholder = "-- Select --"
        self.stages = [self.placeholder] + (stages or [])
        self.centers = [self.placeholder] + (centers or [])
        self.callback = callback
        self.has_data = has_data
        self.title("Start New Session")
        self.resizable(False, False)
        self.minsize(*MIN_SESSION_SETUP_SIZE)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)

        notice_text = (
            "Using the imported dataset for this session."
            if has_data
            else "No dataset imported yet. A blank roster will be created."
        )
        self.notice_var = ctk.StringVar(value=notice_text)
        self.error_var = ctk.StringVar(value="")

        self.title_font = ctk.CTkFont(size=21, weight="bold")
        self.body_font = ctk.CTkFont(size=13)
        self.label_font = ctk.CTkFont(size=12, weight="bold")

        self.field_bg_color = ("#E8EDF6", "#2C3039")
        self.field_border_color = ("#CBD5E1", "#3D4452")
        self.field_button_color = ("#D9E2F0", "#3F4656")
        self.icon_color = ("#4B5563", "#A0AEC0")
        self.error_color = "#b00020"

        self._build_form()
        ensure_initial_size(self, min_size=MIN_SESSION_SETUP_SIZE)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Return>", lambda _e: self._on_submit())
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self._focus_after_id = None
        # Give time for widgets to be properly created and mapped
        self.after(100, self._initialize_window)

    def _build_form(self):
        content = CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        content.grid_columnconfigure(0, weight=1)

        row = 0
        CTkLabel(
            content,
            text="Start New Session",
            font=self.title_font,
            anchor="w",
        ).grid(row=row, column=0, sticky="ew")
        row += 1
        CTkLabel(
            content,
            textvariable=self.notice_var,
            font=self.body_font,
            justify="left",
            anchor="w",
            wraplength=360,
        ).grid(row=row, column=0, sticky="ew", pady=(8, 20))
        row += 1

        row = self._add_combo_field(content, row, "Stage", "stage_cb", self.stages)
        row = self._add_combo_field(content, row, "Center", "center_cb", self.centers)

        CTkLabel(
            content,
            text="Session No.",
            font=self.label_font,
            anchor="w",
        ).grid(row=row, column=0, sticky="w")
        row += 1
        session_container = CTkFrame(
            content,
            fg_color=self.field_bg_color,
            corner_radius=16,
            border_width=1,
            border_color=self.field_border_color,
        )
        session_container.grid(row=row, column=0, sticky="ew", pady=(6, 20))
        session_container.grid_columnconfigure(1, weight=1)

        CTkLabel(
            session_container,
            text="#",
            font=self.label_font,
            width=28,
            anchor="center",
            text_color=self.icon_color,
        ).grid(row=0, column=0, padx=(12, 8), pady=10)

        self.session_ent = CTkEntry(
            session_container,
            border_width=0,
            corner_radius=10,
            fg_color="transparent",
            font=self.body_font,
        )
        self.session_ent.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=10)

        row += 1
        CTkLabel(
            content,
            textvariable=self.error_var,
            font=self.body_font,
            text_color=self.error_color,
            justify="left",
            anchor="w",
            wraplength=360,
        ).grid(row=row, column=0, sticky="ew", pady=(0, 4))

        row += 1
        btn_frame = CTkFrame(content, fg_color="transparent")
        btn_frame.grid(row=row, column=0, sticky="e", pady=(24, 0))
        CTkButton(
            btn_frame,
            text="Start Session",
            command=self._on_submit,
            corner_radius=18,
        ).pack(side="right")
        CTkButton(
            btn_frame,
            text="Cancel",
            command=self._on_cancel,
            fg_color="transparent",
            hover_color=("#E5E7EB", "#2E2E2E"),
            text_color=("#4B5563", "#A0AEC0"),
            border_width=0,
            corner_radius=18,
        ).pack(side="right", padx=(0, 12))

    def _add_combo_field(self, parent, start_row, label_text, attr_name, values):
        CTkLabel(
            parent,
            text=label_text,
            font=self.label_font,
            anchor="w",
        ).grid(row=start_row, column=0, sticky="w")
        combo = CTkComboBox(
            parent,
            values=values,
            state="readonly",
            font=self.body_font,
            corner_radius=16,
            border_width=0,
            fg_color=self.field_bg_color,
            button_color=self.field_button_color,
            button_hover_color=self.field_button_color,
            dropdown_fg_color=self.field_bg_color,
            dropdown_hover_color=self.field_button_color,
        )
        combo.grid(row=start_row + 1, column=0, sticky="ew", pady=(6, 16))
        combo.set(self.placeholder)
        setattr(self, attr_name, combo)
        return start_row + 2

    def _center_on_parent(self):
        self.update_idletasks()
        width = self.winfo_width() or self.winfo_reqwidth()
        height = self.winfo_height() or self.winfo_reqheight()
        px = self.parent.winfo_rootx()
        py = self.parent.winfo_rooty()
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()
        x = px + max((pw - width) // 2, 0) if pw else px
        y = py + max((ph - height) // 2, 0) if ph else py
        self.geometry(f"{width}x{height}+{x}+{y}")
        bring_window_to_front(self)

    def _initialize_window(self):
        """Initialize window position and focus after widgets are mapped."""
        self._center_on_parent()
        if self.winfo_exists():
            self.session_ent.focus_set()

    def _on_submit(self):
        stage = self.stage_cb.get().strip()
        center = self.center_cb.get().strip()
        session_no = self.session_ent.get().strip()
        if stage == self.placeholder or center == self.placeholder or not session_no.isdigit():
            self.error_var.set("Select stage, center, and enter a numeric session number.")
            return
        self.error_var.set("")
        payload = {
            "stage": stage,
            "center": center,
            "no": int(session_no),
            "name": f"{stage} {center} session {int(session_no)}"
        }
        if self._focus_after_id:
            self.after_cancel(self._focus_after_id)
            self._focus_after_id = None
        if self.callback:
            self.callback(payload)
            self.callback = None
        self.destroy()

    def _on_cancel(self):
        if self._focus_after_id:
            self.after_cancel(self._focus_after_id)
            self._focus_after_id = None
        if self.callback:
            self.callback(None)
            self.callback = None
        self.destroy()
