import customtkinter as ctk
from customtkinter import CTkFrame, CTkLabel, CTkProgressBar


class ScanStatsStrip(CTkFrame):
    def __init__(self, parent, *, load_icon, show_exam=False, show_homework=False):
        super().__init__(parent, fg_color="#12263a", corner_radius=12, height=56)
        self._load_icon = load_icon
        self._progress_bar = None
        self._value_vars = {
            "total": ctk.StringVar(value="0"),
            "attended": ctk.StringVar(value="0"),
            "percent": ctk.StringVar(value="0%"),
            "missing_exam": ctk.StringVar(value="0"),
            "missing_hw": ctk.StringVar(value="0"),
        }
        self._build(show_exam=show_exam, show_homework=show_homework)

    def update_metrics(self, metrics):
        self._value_vars["total"].set(f"{metrics['total']}")
        self._value_vars["attended"].set(f"{metrics['attended']}")
        self._value_vars["percent"].set(metrics["attendance_rate"])
        if "missing_exam" in metrics:
            self._value_vars["missing_exam"].set(f"{metrics['missing_exam']}")
        if "missing_hw" in metrics:
            self._value_vars["missing_hw"].set(f"{metrics['missing_hw']}")
        if self._progress_bar is not None:
            self._progress_bar.set(self._parse_percent(metrics["attendance_rate"]))

    def _build(self, *, show_exam, show_homework):
        card_defs = [
            {"label": "Total Students", "key": "total", "icon": "group.png", "is_progress": False},
            {"label": "Attended", "key": "attended", "icon": "check_circle.png", "is_progress": False},
            {"label": "Attendance", "key": "percent", "icon": "group.png", "is_progress": True},
        ]
        if show_exam:
            card_defs.append({"label": "Missing Exam", "key": "missing_exam", "icon": "warning.png", "is_progress": False})
        if show_homework:
            card_defs.append({"label": "Missing Homework", "key": "missing_hw", "icon": "warning.png", "is_progress": False})

        for idx, card in enumerate(card_defs):
            card_frame = CTkFrame(self, fg_color="#232a36", corner_radius=10, width=110, height=56)
            card_frame.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 10, 0), pady=4)
            self.grid_columnconfigure(idx, weight=1)

            card_inner = CTkFrame(card_frame, fg_color="transparent")
            card_inner.pack(expand=True, fill="both")

            CTkLabel(
                card_inner,
                text=card["label"],
                font=("Roboto", 12, "bold"),
                text_color="#cac4d0",
                anchor="center",
                justify="center",
            ).pack(side="top", anchor="center", pady=(6, 0))

            icon_num_frame = CTkFrame(card_inner, fg_color="transparent")
            icon_num_frame.pack(side="top", anchor="center", pady=(0, 0), expand=True)
            icon_img = self._load_icon(card["icon"], size=(22, 22))
            icon_label = CTkLabel(icon_num_frame, image=icon_img, text="", width=24)
            icon_label.pack(side="left", anchor="center", padx=(0, 4))

            if card["is_progress"]:
                progress = CTkProgressBar(icon_num_frame, width=40, height=6)
                progress.set(self._parse_percent(self._value_vars["percent"].get()))
                progress.pack(side="left", anchor="center", padx=(0, 4))
                self._progress_bar = progress
                CTkLabel(
                    icon_num_frame,
                    textvariable=self._value_vars["percent"],
                    font=("Roboto", 18, "bold"),
                    text_color="#a9c8e7",
                    anchor="center",
                    justify="center",
                ).pack(side="left", anchor="center")
            else:
                CTkLabel(
                    icon_num_frame,
                    textvariable=self._value_vars[card["key"]],
                    font=("Roboto", 20, "bold"),
                    text_color="#e3e2e6",
                    anchor="center",
                    justify="center",
                ).pack(side="left", anchor="center")

    def _parse_percent(self, value):
        try:
            return float(str(value).replace("%", "")) / 100.0
        except Exception:
            return 0.0