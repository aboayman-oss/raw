import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.focus_view_state import build_focus_view_state, format_focus_grade
from core.scan_filters import apply_task_filter_change, clear_filter_values, is_filter_active
from core.session_manager import SessionManager
from core.grade_logic import grade_is_zero, grade_missing_or_zero
from core.session_mutations import build_manual_add_record, prepare_attendance_update
from core.scan_workflow import build_focus_action_payload, build_manual_add_default_notes
from core.scan_view_logic import build_scan_context, collect_missing_tasks, row_matches_filters
from utils.helpers import (
    APP_STORAGE_DIRNAME,
    SESSION_LAST_ACTION_COL,
    SESSION_MANUAL_ADDED_COL,
    compute_session_summary,
    resolve_base_folder,
    sanitize_settings_payload,
)


class SessionLogicTests(unittest.TestCase):
    def test_focus_view_state_formats_missing_and_zero_grades(self):
        state = build_focus_view_state(
            "missing_exam",
            {"missing_tasks": ["exam"], "exam": "0", "homework": "8"},
        )

        self.assertEqual(state["status_icon"], "warning.png")
        self.assertEqual(state["exam"]["text"], "0 (Fail)")
        self.assertEqual(state["homework"]["text"], "8")
        self.assertEqual(state["buttons"], ["deny", "override", "complete"])

    def test_focus_view_state_uses_cancel_for_already_attended(self):
        state = build_focus_view_state(
            "ok",
            {"already_attended": True, "exam": "", "homework": ""},
        )

        self.assertEqual(state["buttons"], ["cancel"])
        self.assertEqual(state["exam"]["text"], "Not Submitted")

    def test_resolve_base_folder_uses_runtime_dir_for_writable_frozen_build(self):
        resolved = resolve_base_folder(
            r"C:\Apps\RFIDAttendanceManager",
            frozen=True,
            is_writable=True,
            local_appdata=r"C:\Users\Ahmed\AppData\Local",
        )
        self.assertEqual(resolved, r"C:\Apps\RFIDAttendanceManager")

    def test_resolve_base_folder_falls_back_to_local_appdata_when_read_only(self):
        resolved = resolve_base_folder(
            r"C:\Program Files\RFIDAttendanceManager",
            frozen=True,
            is_writable=False,
            local_appdata=r"C:\Users\Ahmed\AppData\Local",
        )
        self.assertEqual(resolved, rf"C:\Users\Ahmed\AppData\Local\{APP_STORAGE_DIRNAME}")

    def test_sanitize_settings_payload_resets_sessions_folder(self):
        settings = sanitize_settings_payload(
            {"sessions_folder": r"D:\Old", "file_type": "xlsx"},
            r"C:\Users\Ahmed\Attendance\Sessions",
        )
        self.assertEqual(settings["sessions_folder"], r"C:\Users\Ahmed\Attendance\Sessions")
        self.assertEqual(settings["file_type"], "xlsx")

    def test_scan_filter_helpers_toggle_and_clear(self):
        filters = {
            "attendance": "all",
            "missing_exam": True,
            "missing_hw": False,
            "has_exam": True,
            "has_hw": False,
            "has_notes": False,
            "manual_added": False,
        }
        updated = apply_task_filter_change(filters, "exam", "missing")
        self.assertFalse(updated["has_exam"])
        self.assertTrue(is_filter_active(updated))
        self.assertEqual(clear_filter_values(updated)["attendance"], "all")
        self.assertFalse(is_filter_active(clear_filter_values(updated)))

    def test_grade_logic_handles_fraction_and_blank(self):
        self.assertTrue(grade_is_zero("0/10"))
        self.assertTrue(grade_missing_or_zero(""))
        self.assertFalse(grade_missing_or_zero("2/10"))
        self.assertEqual(format_focus_grade("0/10"), "0/10 (Fail)")

    def test_prepare_attendance_update_preserves_existing_timestamp(self):
        payload, column_timestamp, is_first_attend = prepare_attendance_update(
            {"student_id": "10", "timestamp": "09:00:00 AM", "notes": "", "attendance": "attend"},
            "00000001",
            "attend",
            "note",
            pd.Timestamp("2026-03-08 10:30:00").to_pydatetime(),
            action="attend",
        )
        self.assertFalse(is_first_attend)
        self.assertEqual(column_timestamp, "09:00:00 AM")
        self.assertEqual(payload["timestamp"], "09:00:00 AM")
        self.assertEqual(payload[SESSION_LAST_ACTION_COL], "attend")

    def test_build_manual_add_record_sets_metadata(self):
        payload = build_manual_add_record(
            "Unknown 1",
            {"student_id": "12", "name": "Bob", "phone": "0101"},
            "manual",
            pd.Timestamp("2026-03-08 11:00:00").to_pydatetime(),
            {"exam": True, "homework": True},
        )
        self.assertEqual(payload["attendance"], "attend")
        self.assertEqual(payload[SESSION_MANUAL_ADDED_COL], "true")
        self.assertEqual(payload[SESSION_LAST_ACTION_COL], "attend")
        self.assertIn("manual", payload["notes"])
        self.assertIn("exam", payload)
        self.assertIn("homework", payload)

    def test_collect_missing_tasks_uses_restrictions(self):
        missing = collect_missing_tasks({"exam": "0", "homework": "5"}, {"exam": True, "homework": True})
        self.assertEqual(missing, ["exam"])

    def test_build_scan_context_marks_already_attended(self):
        context = build_scan_context(
            "00000001",
            {
                "card_id": "00000001",
                "name": "Alice",
                "student_id": "10",
                "attendance": "attend",
                "notes": "",
                "timestamp": "10:00:00 AM",
                "exam": "5",
                "homework": "5",
                "_restrictions": {"exam": True, "homework": True},
            },
            normalized_iid="00000001",
        )
        self.assertEqual(context["status"], "already_attended")
        self.assertTrue(context["allow_cancel"])

    def test_row_matches_filters_combines_search_and_flags(self):
        row = {"name": "Alice", "attendance": "attend", "notes": "has note", "exam": "5", "homework": "0"}
        filters = {
            "attendance": "attend",
            "missing_exam": False,
            "missing_hw": True,
            "has_exam": False,
            "has_hw": False,
            "has_notes": True,
            "manual_added": False,
        }
        self.assertTrue(row_matches_filters(row, "00000001", ["alice"], filters, {"exam": True, "homework": True}))
        self.assertFalse(row_matches_filters(row, "00000001", ["bob"], filters, {"exam": True, "homework": True}))

    def test_build_focus_action_payload_completed(self):
        payload = build_focus_action_payload(
            "completed",
            {"existing_notes": "old", "missing_tasks": ["exam", "homework"]},
            "typed",
            pd.Timestamp("2026-03-08 10:30:00").to_pydatetime(),
        )

        self.assertEqual(payload["attendance"], "attend")
        self.assertEqual(payload["record_action"], "attend")
        self.assertEqual(payload["column_timestamp"], "10:30:00 AM")
        self.assertIn("Completed Exam & Homework at center.", payload["final_note"])
        self.assertTrue(payload["final_note"].endswith("typed"))

    def test_build_manual_add_default_notes_marks_diff_group(self):
        result = build_manual_add_default_notes({"status": "not_found", "found": False}, "note", "(From diff Group)")
        self.assertEqual(result, "(From diff Group) note")

    def test_compute_session_summary_prefers_persisted_metadata(self):
        df = pd.DataFrame(
            {
                "card_id": ["00000001", "Unknown 1", "00000003"],
                "attendance": ["attend", "attend", ""],
                "notes": ["", "manual", "canceled note"],
                "exam": ["10", "0", "0"],
                "homework": ["5", "", "0"],
                SESSION_MANUAL_ADDED_COL: ["", "true", "false"],
                SESSION_LAST_ACTION_COL: ["attend", "attend", "canceled"],
            }
        )

        summary = compute_session_summary(
            df,
            {"attendance": "attendance", "notes": "notes", "card_id": "card_id", "exam": "exam", "homework": "homework"},
            {"exam": True, "homework": True},
        )

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["attended"], 2)
        self.assertEqual(summary["manual_additions"], 1)
        self.assertEqual(summary["cancellations"], 1)
        self.assertEqual(summary["missing_exam"], 2)
        self.assertEqual(summary["missing_hw"], 2)

    def test_add_record_marks_dirty_without_immediate_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_path = os.path.join(temp_dir, "session.csv")
            initial_df = pd.DataFrame(
                {
                    "card_id": ["00000001"],
                    "student_id": ["10"],
                    "name": ["Alice"],
                    "phone": ["0100"],
                    "attendance": [""],
                    "notes": [""],
                    "timestamp": [""],
                }
            )
            initial_df.to_csv(session_path, index=False)

            manager = SessionManager(
                "session",
                {},
                {
                    "card_id": "card_id",
                    "student_id": "student_id",
                    "name": "name",
                    "phone": "phone",
                    "attendance": "attendance",
                    "notes": "notes",
                    "timestamp": "timestamp",
                },
                initial_df,
                session_path=session_path,
            )

            manager.add_record(
                {
                    "card_id": "00000001",
                    "attendance": "attend",
                    "notes": "updated",
                    "timestamp": "2026-03-08 10:00",
                }
            )

            disk_df = pd.read_csv(session_path, dtype=str).fillna("")
            self.assertEqual(disk_df.loc[0, "attendance"], "")
            self.assertTrue(manager.has_pending_changes())

            manager.save()

            disk_df = pd.read_csv(session_path, dtype=str).fillna("")
            self.assertEqual(disk_df.loc[0, "attendance"], "attend")
            self.assertEqual(disk_df.loc[0, "notes"], "updated")
            self.assertFalse(manager.has_pending_changes())

    def test_add_record_new_row_persists_metadata_on_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_path = os.path.join(temp_dir, "session.csv")
            initial_df = pd.DataFrame(
                {
                    "card_id": [],
                    "student_id": [],
                    "name": [],
                    "phone": [],
                    "attendance": [],
                    "notes": [],
                    "timestamp": [],
                }
            )

            manager = SessionManager(
                "session",
                {},
                {
                    "card_id": "card_id",
                    "student_id": "student_id",
                    "name": "name",
                    "phone": "phone",
                    "attendance": "attendance",
                    "notes": "notes",
                    "timestamp": "timestamp",
                },
                initial_df,
                session_path=session_path,
            )

            manager.add_record(
                {
                    "card_id": "Unknown 1",
                    "student_id": "12",
                    "name": "Bob",
                    "phone": "0101",
                    "attendance": "attend",
                    "notes": "manual",
                    "timestamp": "2026-03-08 11:00",
                    SESSION_MANUAL_ADDED_COL: "true",
                    SESSION_LAST_ACTION_COL: "attend",
                }
            )
            manager.save()

            disk_df = pd.read_csv(session_path, dtype=str).fillna("")
            self.assertEqual(len(disk_df.index), 1)
            self.assertEqual(disk_df.loc[0, SESSION_MANUAL_ADDED_COL], "true")
            self.assertEqual(disk_df.loc[0, SESSION_LAST_ACTION_COL], "attend")

    def test_session_manager_duplicate_lookup_uses_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_path = os.path.join(temp_dir, "session.csv")
            initial_df = pd.DataFrame(
                {
                    "card_id": ["00000001"],
                    "student_ref": ["10"],
                    "phone_ref": ["0100"],
                    "attendance": [""],
                    "notes": [""],
                    "timestamp": [""],
                }
            )
            initial_df.to_csv(session_path, index=False)

            manager = SessionManager(
                "session",
                {},
                {
                    "card_id": "card_id",
                    "student_id": "student_ref",
                    "phone": "phone_ref",
                    "attendance": "attendance",
                    "notes": "notes",
                    "timestamp": "timestamp",
                },
                initial_df,
                session_path=session_path,
            )

            id_exists, phone_exists = manager.has_student_id_or_phone("10", "0100")
            self.assertTrue(id_exists)
            self.assertTrue(phone_exists)


if __name__ == "__main__":
    unittest.main()