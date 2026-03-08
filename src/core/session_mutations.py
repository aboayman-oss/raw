"""Pure helpers for building session mutation payloads."""

from utils.helpers import SESSION_LAST_ACTION_COL, SESSION_MANUAL_ADDED_COL

from .scan_workflow import clean_text, format_column_timestamp, format_note_tag


TRACKED_ROW_FIELDS = ("student_id", "name", "phone", "exam", "homework")


def build_record_payload(row, card_id, attendance, notes, timestamp):
    payload = {field: clean_text(row.get(field, "")) for field in TRACKED_ROW_FIELDS if field in row}
    payload.update(
        {
            "card_id": clean_text(card_id),
            "attendance": clean_text(attendance),
            "notes": clean_text(notes),
            "timestamp": clean_text(timestamp),
        }
    )
    return payload


def prepare_attendance_update(row, card_id, attendance, notes, current_dt, *, timestamp_override=None, action=None):
    target_attendance = clean_text(attendance)
    existing_timestamp = clean_text(row.get("timestamp", ""))
    override_clean = clean_text(timestamp_override)
    is_first_attend = target_attendance.lower() == "attend" and not existing_timestamp
    column_timestamp = override_clean or existing_timestamp if not is_first_attend else (override_clean or format_column_timestamp(current_dt))
    payload = build_record_payload(row, card_id, target_attendance, notes, column_timestamp)
    if action:
        payload[SESSION_LAST_ACTION_COL] = action
    return payload, clean_text(column_timestamp), is_first_attend


def build_manual_add_record(card_id, values, default_notes, current_dt, restrictions):
    note_tag = format_note_tag(current_dt)
    default_notes_clean = clean_text(default_notes)
    note_text = f"{note_tag} {default_notes_clean}".strip() if default_notes_clean else note_tag
    payload = {
        "card_id": clean_text(card_id),
        "attendance": "attend",
        "timestamp": format_column_timestamp(current_dt),
        "notes": note_text,
        SESSION_MANUAL_ADDED_COL: "true",
        SESSION_LAST_ACTION_COL: "attend",
    }
    payload.update({key: clean_text(value) for key, value in (values or {}).items()})
    for task in ("exam", "homework"):
        if restrictions.get(task):
            payload.setdefault(task, "")
    return payload