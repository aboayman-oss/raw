from core.grade_logic import grade_is_zero


SUCCESS_ICON = "task_alt.png"
PROBLEM_ICON = "error.png"
SUCCESS_COLOR = "#1b331d"
PROBLEM_COLOR = "#3c1b1a"

STATUS_ICONS = {
    "ok": "check_circle.png",
    "already_attended": "gpp_good.png",
    "missing_exam": "warning.png",
    "missing_homework": "warning.png",
    "not_found": "person_add.png",
    "duplicate": "error.png",
}

ACTION_BUTTONS = {
    "not_found": ["add_student"],
    "missing_exam": ["deny", "override", "complete"],
    "missing_homework": ["deny", "override", "complete"],
    "already_attended": ["cancel"],
}


def format_focus_grade(value):
    if value in (None, ""):
        return "Not Submitted"

    text = str(value)
    if grade_is_zero(value):
        text += " (Fail)"
    return text


def _build_task_state(task_name, value, missing_tasks):
    is_missing = task_name in set(missing_tasks or [])
    return {
        "icon": PROBLEM_ICON if is_missing else SUCCESS_ICON,
        "text": format_focus_grade(value),
        "color": PROBLEM_COLOR if is_missing else SUCCESS_COLOR,
    }


def build_focus_view_state(kind, context):
    status = kind or "ok"
    button_key = "already_attended" if context.get("already_attended") else status

    return {
        "status_icon": STATUS_ICONS.get(status, STATUS_ICONS["ok"]),
        "homework": _build_task_state("homework", context.get("homework", ""), context.get("missing_tasks", [])),
        "exam": _build_task_state("exam", context.get("exam", ""), context.get("missing_tasks", [])),
        "buttons": ACTION_BUTTONS.get(button_key, []),
    }