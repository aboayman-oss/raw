"""Pure workflow helpers for scan-session mutations."""

FOCUS_ACTION_SPECS = {
    "completed": {
        "attendance": "attend",
        "record_action": "attend",
        "template": "Completed {desc} at center.",
        "fallback_desc": "task",
    },
    "override": {
        "attendance": "attend",
        "record_action": "attend",
        "template": "Attended (Didn't do {desc}).",
        "fallback_desc": "task",
    },
    "denied": {
        "attendance": "",
        "record_action": "denied",
        "template": "Denied Entry: No {desc}.",
        "fallback_desc": "requirements",
    },
    "canceled": {
        "attendance": "",
        "record_action": "canceled",
        "template": "Canceled.",
        "fallback_desc": "",
    },
}


def clean_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def describe_tasks(tasks):
    if not tasks:
        return ""
    labels = {"exam": "Exam", "homework": "Homework"}
    mapped = [labels.get(task, str(task).title()) for task in tasks]
    if not mapped:
        return ""
    return mapped[0] if len(mapped) == 1 else " & ".join(mapped)


def append_notes(original, addition):
    original_clean = clean_text(original)
    addition_clean = clean_text(addition)
    if not addition_clean:
        return original_clean
    if not original_clean:
        return addition_clean
    return f"{original_clean.rstrip()}\n{addition_clean}"


def format_column_timestamp(dt):
    return dt.strftime("%I:%M:%S %p")


def format_note_tag(dt):
    return f"[{dt.strftime('%I:%M:%S %p')}]"


def build_focus_action_payload(action_name, context, typed_note, current_dt):
    spec = FOCUS_ACTION_SPECS[action_name]
    note_tag = format_note_tag(current_dt)
    desc = describe_tasks((context or {}).get("missing_tasks", [])) or spec["fallback_desc"]
    action_note = spec["template"].format(desc=desc).strip()
    if action_note:
        action_note = f"{note_tag} {action_note}"
    base = append_notes((context or {}).get("existing_notes", ""), action_note)
    final_note = append_notes(base, typed_note)
    return {
        "attendance": spec["attendance"],
        "record_action": spec["record_action"],
        "column_timestamp": format_column_timestamp(current_dt),
        "final_note": final_note,
    }


def build_manual_add_default_notes(context, typed_note, diff_group_note):
    context = context or {}
    default_notes = clean_text(typed_note)
    if not context.get("found", True) or context.get("status") == "not_found":
        return f"{diff_group_note} {default_notes}".strip() if default_notes else diff_group_note
    return default_notes