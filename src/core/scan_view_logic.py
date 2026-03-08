"""Pure helpers for scan row status, context, and filtering."""

from .grade_logic import grade_missing_or_zero
from .scan_workflow import clean_text


def collect_missing_tasks(row, restrictions):
    missing = []
    if restrictions.get("exam") and grade_missing_or_zero(row.get("exam", "")):
        missing.append("exam")
    if restrictions.get("homework") and grade_missing_or_zero(row.get("homework", "")):
        missing.append("homework")
    return missing


def determine_scan_status(scan_ctx):
    if scan_ctx.get("status") in {"not_found", "duplicate"}:
        return scan_ctx["status"]
    if not scan_ctx.get("found", True):
        return "not_found"
    if scan_ctx.get("already_attended"):
        return "already_attended"
    missing = scan_ctx.get("missing_tasks", [])
    if missing:
        return "missing_exam" if "exam" in missing else "missing_homework"
    return "ok"


def build_scan_context(iid, row, *, source="manual", normalized_iid="", card_id_override=None):
    card_display = clean_text(card_id_override or row.get("card_id") or normalized_iid)
    attendance = clean_text(row.get("attendance", "")).lower()
    context = {
        "iid": iid,
        "card_id": clean_text(card_id_override or normalized_iid),
        "card_display": card_display,
        "name": clean_text(row.get("name", "")),
        "student_id": clean_text(row.get("student_id", "")),
        "attendance": attendance,
        "existing_notes": clean_text(row.get("notes", "")),
        "timestamp": clean_text(row.get("timestamp", "")),
        "source": source,
        "focus_iids": [iid],
        "found": True,
        "homework": clean_text(row.get("homework", "")),
        "exam": clean_text(row.get("exam", "")),
    }
    context["missing_tasks"] = collect_missing_tasks(context, row.get("_restrictions", {}))
    context["already_attended"] = attendance == "attend"
    context["allow_cancel"] = context["already_attended"]
    context["status"] = determine_scan_status(context)
    context["display_name"] = context["name"] or context["student_id"] or context["card_display"] or "Student"
    return context


def row_matches_filters(row, iid, terms, filters, restrictions):
    search_values = [clean_text(value).lower() for value in row.values()]
    haystack = " ".join(search_values + [clean_text(iid).lower()])
    if terms and not all(term in haystack for term in terms):
        return False

    attendance = clean_text(row.get("attendance", "")).lower()
    if filters.get("attendance") == "attend" and attendance != "attend":
        return False
    if filters.get("attendance") == "absent" and attendance == "attend":
        return False

    missing_tasks = collect_missing_tasks(row, restrictions)
    if filters.get("missing_exam") and "exam" not in missing_tasks:
        return False
    if filters.get("missing_hw") and "homework" not in missing_tasks:
        return False
    if filters.get("has_exam") and "exam" in missing_tasks:
        return False
    if filters.get("has_hw") and "homework" in missing_tasks:
        return False

    if filters.get("has_notes") and not clean_text(row.get("notes", "")):
        return False
    if filters.get("manual_added") and clean_text(iid).isdigit():
        return False
    return True