"""Helpers for scan filter state."""


FILTER_DEFAULTS = {
    "attendance": "all",
    "missing_exam": False,
    "missing_hw": False,
    "has_exam": False,
    "has_hw": False,
    "has_notes": False,
    "manual_added": False,
}


def is_filter_active(filters):
    for key, default in FILTER_DEFAULTS.items():
        if filters.get(key) != default:
            return True
    return False


def clear_filter_values(filters):
    return dict(FILTER_DEFAULTS)


def apply_task_filter_change(filters, task_type, state):
    updated = dict(filters)
    if task_type == "exam":
        if state == "missing" and updated.get("missing_exam"):
            updated["has_exam"] = False
        elif state == "has" and updated.get("has_exam"):
            updated["missing_exam"] = False
    elif task_type == "hw":
        if state == "missing" and updated.get("missing_hw"):
            updated["has_hw"] = False
        elif state == "has" and updated.get("has_hw"):
            updated["missing_hw"] = False
    return updated