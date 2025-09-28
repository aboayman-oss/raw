"""Dialog that summarizes session statistics and provides file access shortcuts."""
import os
import subprocess
import sys
from tkinter import messagebox
from PIL import Image

from customtkinter import CTkButton, CTkFrame, CTkLabel, CTkToplevel, CTkImage

from utils.helpers import MIN_SUMMARY_SIZE, bring_window_to_front, ensure_initial_size, ASSETS_DIR

class SessionSummaryDialog(CTkToplevel):
    def __init__(self, parent, *, session_name, summary, session_path, params=None, read_only=False):
        super().__init__(parent)
        self.parent = parent
        self.session_name = session_name
        self.summary = summary or {}
        self.session_path = session_path
        self.params = params or {}
        self.read_only = read_only

        self.title("Session Summary")
        self.minsize(*MIN_SUMMARY_SIZE)
        self.transient(parent)
        self.grab_set()
        self.after(40, lambda: bring_window_to_front(self))

        container = CTkFrame(self, corner_radius=16, fg_color="#1a1d23")
        container.pack(fill="both", expand=True, padx=24, pady=24)
        container.grid_columnconfigure(0, weight=1)

        header = CTkFrame(container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        CTkLabel(header, text="Session Summary", font=("Arial", 24, "bold")).grid(row=0, column=0, sticky="w")

        # Display Session Name
        details_frame = CTkFrame(header, fg_color="transparent")
        details_frame.grid(row=1, column=0, sticky="w", pady=(4, 0))

        session_display_name = os.path.splitext(os.path.basename(self.session_path))[0] if self.session_path else self.session_name
        CTkLabel(details_frame, text=session_display_name, font=("Arial", 15, "bold"), text_color=("#1f6aa5", "#a9c8e7")).pack(side="left")

        if read_only:
            CTkLabel(header, text="Read-only session", font=("Arial", 14), text_color="#64748b").grid(row=2, column=0, sticky="w", pady=(8, 0))

        metrics_frame = CTkFrame(container, fg_color="transparent")
        metrics_frame.grid(row=1, column=0, sticky="ew", pady=(18, 12))
        metrics_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="metrics_cols")

        # --- Helper to create a metric row ---
        def create_metric_row(parent, label, value):
            row = CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, 4))
            row.grid_columnconfigure(1, weight=1)
            CTkLabel(row, text=label, font=("Arial", 14, "bold"), text_color="#111827").grid(row=0, column=0, sticky="w")
            CTkLabel(row, text=value, font=("Arial", 14, "bold"), text_color="#111827").grid(row=0, column=1, sticky="e")

        # --- Card 1: Overview ---
        overview_card = CTkFrame(metrics_frame, fg_color=("#f8fafc", "#ffffff"), corner_radius=12, border_width=1, border_color="#343a46")
        overview_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        overview_card.pack_propagate(False)

        title_frame_1 = CTkFrame(overview_card, fg_color="#232a36", corner_radius=0)
        title_frame_1.pack(fill="x", side="top")
        title_frame_1.grid_columnconfigure(1, weight=1) # Make the center column expandable

        # Load and place the icon
        try:
            icon_path = os.path.join(ASSETS_DIR, "location_home.png")
            icon_image = CTkImage(Image.open(icon_path), size=(20, 20))
            CTkLabel(title_frame_1, image=icon_image, text="").grid(row=0, column=0, padx=(12, 5), pady=8)
        except Exception as e:
            print(f"Warning: Could not load 'location_home.png' icon: {e}")

        CTkLabel(title_frame_1, text="Overview", font=("Arial", 16, "bold")).grid(row=0, column=1, pady=8)
        overview_content = CTkFrame(overview_card, fg_color="transparent")
        overview_content.pack(fill="both", expand=True, padx=12, pady=10)

        if (total := self.summary.get("total")) is not None:
            create_metric_row(overview_content, "Total students:", f"{total:,}")
        if (attended := self.summary.get("attended")) is not None:
            create_metric_row(overview_content, "Attended:", f"{attended:,}")
        if (manual := self.summary.get("manual_additions")) is not None:
            create_metric_row(overview_content, "Manual additions:", f"{manual:,}")

        # --- Card 2: Attendance Rate ---
        rate_card = CTkFrame(metrics_frame, fg_color=("#f8fafc", "#ffffff"), corner_radius=12, border_width=1, border_color="#343a46")
        rate_card.grid(row=0, column=1, sticky="nsew", padx=(4, 4))
        rate_card.pack_propagate(False)
        title_frame_2 = CTkFrame(rate_card, fg_color="#232a36", corner_radius=0)
        title_frame_2.pack(fill="x", side="top")
        title_frame_2.grid_columnconfigure(1, weight=1) # Make the center column expandable

        # Load and place the icon
        try:
            icon_path = os.path.join(ASSETS_DIR, "bar_chart.png")
            icon_image = CTkImage(Image.open(icon_path), size=(20, 20))
            CTkLabel(title_frame_2, image=icon_image, text="").grid(row=0, column=0, padx=(12, 5), pady=8)
        except Exception as e:
            print(f"Warning: Could not load 'bar_chart.png' icon: {e}")

        CTkLabel(title_frame_2, text="Attendance Rate", font=("Arial", 16, "bold")).grid(row=0, column=1, pady=8)
        rate_content = CTkFrame(rate_card, fg_color="transparent")
        rate_content.pack(fill="both", expand=True, padx=12, pady=10)
        if (rate := self.summary.get("attendance_rate")) is not None:
            try:
                rate_value = float(rate.strip('%'))
            except (ValueError, TypeError):
                rate_value = 0.0

            # Determine color based on rate
            if rate_value > 80:
                text_color = "#22c55e"  # Green
            elif rate_value < 50:
                text_color = "#ef4444"  # Red
            else:
                # Use a neutral color that works on the card's light background
                text_color = "#111827"  # Black/Dark Gray

            CTkLabel(rate_content, text=rate, font=("Arial", 30, "bold"), text_color=text_color).pack(expand=True)

        # --- Card 3: Issues ---
        issues_card = CTkFrame(metrics_frame, fg_color=("#f8fafc", "#ffffff"), corner_radius=12, border_width=1, border_color="#343a46")
        issues_card.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        issues_card.pack_propagate(False)
        title_frame_3 = CTkFrame(issues_card, fg_color="#232a36", corner_radius=0)
        title_frame_3.pack(fill="x", side="top")
        title_frame_3.grid_columnconfigure(1, weight=1) # Make the center column expandable

        # Load and place the icon
        try:
            icon_path = os.path.join(ASSETS_DIR, "shield_person.png")
            icon_image = CTkImage(Image.open(icon_path), size=(20, 20))
            CTkLabel(title_frame_3, image=icon_image, text="").grid(row=0, column=0, padx=(12, 5), pady=8)
        except Exception as e:
            print(f"Warning: Could not load 'shield_person.png' icon: {e}")

        CTkLabel(title_frame_3, text="Issues & Flags", font=("Arial", 16, "bold")).grid(row=0, column=1, pady=8)
        issues_content = CTkFrame(issues_card, fg_color="transparent")
        issues_content.pack(fill="both", expand=True, padx=12, pady=10)

        if (cancels := self.summary.get("cancellations")) is not None:
            create_metric_row(issues_content, "Cancellations:", f"{cancels:,}")
        if (missing_exam := self.summary.get("missing_exam")) is not None:
            create_metric_row(issues_content, "Missing exam:", f"{missing_exam:,}")
        if (missing_hw := self.summary.get("missing_hw")) is not None:
            create_metric_row(issues_content, "Missing homework:", f"{missing_hw:,}")

        actions = CTkFrame(container, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(24, 0))

        close_button = CTkButton(actions, text="Close", command=self._on_close)
        close_button.pack(fill="x", expand=True)

        ensure_initial_size(self, min_size=MIN_SUMMARY_SIZE)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if hasattr(self.parent, "summary_window") and self.parent.summary_window is self:
            self.parent.summary_window = None
        try:
            self.grab_release()
        except Exception:
            pass
        if self.winfo_exists():
            self.destroy()
