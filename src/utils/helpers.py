"""Shared constants and helpers for the RFID Attendance Manager UI."""
import ctypes
import json
import os
import shutil
import sys
import tempfile
from ctypes import byref, c_int, c_uint, c_void_p, c_size_t, wintypes
from pathlib import Path

import pandas as pd

from core.grade_logic import grade_missing_or_zero

INVALID_PATH_CHARS = set('<>::"/\\|?*')

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
WCA_USEDARKMODECOLORS = 26

_DARK_MODE_APP_INITIALIZED = False
APP_STORAGE_DIRNAME = 'RFID Attendance Manager'
DEFAULTS_FOLDER_NAME = 'defaults'


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [("Attribute", c_int), ("Data", c_void_p), ("SizeOfData", c_size_t)]


def get_runtime_base():
    """Return the folder containing the script or executable."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    module_dir = Path(__file__).resolve().parent
    return str(module_dir.parent)


def is_directory_writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        fd, probe_path = tempfile.mkstemp(prefix='.write_test_', dir=path)
        os.close(fd)
        os.remove(probe_path)
        return True
    except OSError:
        return False


def resolve_base_folder(runtime_base, *, frozen, is_writable, local_appdata=None):
    if not frozen:
        return os.path.dirname(runtime_base)
    if is_writable:
        return runtime_base
    appdata_root = local_appdata or os.environ.get('LOCALAPPDATA')
    if not appdata_root:
        appdata_root = os.path.join(str(Path.home()), 'AppData', 'Local')
    return os.path.join(appdata_root, APP_STORAGE_DIRNAME)


def get_assets_dir():
    """Locate bundled assets for development and PyInstaller builds.

    PyInstaller one-file executables extract bundled data into a temporary
    folder exposed via ``sys._MEIPASS``. We read assets from there so the
    binary stays portable.
    """
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', get_runtime_base())
        return os.path.join(base, 'assets')
    script_dir = get_runtime_base()
    local_assets = os.path.join(script_dir, 'assets')
    if os.path.exists(os.path.join(local_assets, 'logo.png')):
        return local_assets
    parent_dir = os.path.dirname(script_dir)
    parent_assets = os.path.join(parent_dir, 'assets')
    if os.path.exists(os.path.join(parent_assets, 'logo.png')):
        return parent_assets
    return local_assets


def get_defaults_dir():
    """Locate packaged defaults used to seed writable runtime data files."""
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', get_runtime_base())
        return os.path.join(base, DEFAULTS_FOLDER_NAME)
    project_root = os.path.dirname(get_runtime_base())
    return os.path.join(project_root, 'Data archive')


def get_base_folder():
    runtime_base = get_runtime_base()
    frozen = bool(getattr(sys, 'frozen', False))
    writable = is_directory_writable(runtime_base) if frozen else True
    base_folder = resolve_base_folder(runtime_base, frozen=frozen, is_writable=writable)
    os.makedirs(base_folder, exist_ok=True)
    return base_folder


RUNTIME_BASE = get_runtime_base()
# Assets live beside the script during development and inside the temporary
# PyInstaller bundle when frozen, so we centralize their path resolution above.
ASSETS_DIR = get_assets_dir()
DEFAULTS_DIR = get_defaults_dir()
BASE_FOLDER = get_base_folder()

LOGO_FILE        = os.path.join(ASSETS_DIR, 'logo.png')
APP_ICON_FILE = os.path.join(ASSETS_DIR, 'app_icon.ico')
PAST_SESSIONS_ICON_FILE = os.path.join(ASSETS_DIR, 'past sessions.png')
SETTINGS_ICON_FILE = os.path.join(ASSETS_DIR, 'settings.png')
IMPORT_ICON_FILE = os.path.join(ASSETS_DIR, 'import.png')
NEW_SESSION_ICON_FILE = os.path.join(ASSETS_DIR, 'add.png')
DASHBOARD_ICON_FILE = os.path.join(ASSETS_DIR, 'dashboard.png')
FOLDER_OPEN_ICON_FILE = os.path.join(ASSETS_DIR, 'folder_open.png')
HOME_BG_FILE     = os.path.join(ASSETS_DIR, 'background.jpg')
SETTINGS_BG_FILE = os.path.join(ASSETS_DIR, 'backgroundnew.jpg')
STATUS_OK_ICON_FILE = os.path.join(ASSETS_DIR, 'check_circle.png')
STATUS_INFO_ICON_FILE = os.path.join(ASSETS_DIR, 'warning.png')
REMOVE_ICON_FILE = os.path.join(ASSETS_DIR, 'close.png')
PLUS_ICON_FILE = os.path.join(ASSETS_DIR, 'add.png')

SESSION_MANUAL_ADDED_COL = '_manual_added'
SESSION_LAST_ACTION_COL = '_last_action'

DATA_FOLDER      = os.path.join(BASE_FOLDER, 'Data')
DEFAULT_SESSIONS_FOLDER = os.path.join(BASE_FOLDER, 'Sessions')
ARCHIVE_FOLDER   = os.path.join(BASE_FOLDER, 'Data archive')
MAPPING_FILE     = os.path.join(ARCHIVE_FOLDER, 'column_map.json')
SETTINGS_FILE    = os.path.join(ARCHIVE_FOLDER, 'app_settings.json')
COLUMN_MAP_TEMPLATE_FILE = os.path.join(DEFAULTS_DIR, 'column_map.json')

MIN_DASHBOARD_SIZE     = (980, 640)
MIN_SCAN_SIZE          = (900, 560)
MIN_SETTINGS_SIZE      = (640, 480)
MIN_SESSION_SETUP_SIZE = (360, 240)
MIN_SUMMARY_SIZE       = (380, 320)
MIN_PAST_SESSIONS_SIZE = (720, 480)

SETTINGS = {
    "sessions_folder": DEFAULT_SESSIONS_FOLDER,
    "stage_options":  ["2nd", "3rd"],
    "center_options": [
        "October", "Ferdous", "Helwan", "Hadayek Helwan",
        "Zayed", "Haram", "Dokki", "Maadi", "15 May"
    ],
    "restrictions": {"exam": True, "homework": True},
    "file_type": "xlsx"

}


def sanitize_settings_payload(settings, default_sessions_folder):
    payload = dict(settings or {})
    payload["sessions_folder"] = default_sessions_folder
    return payload


def _seed_file_if_missing(source_path, target_path):
    if os.path.exists(target_path) or not os.path.exists(source_path):
        return
    shutil.copyfile(source_path, target_path)


def _seed_settings_file_if_missing():
    if os.path.exists(SETTINGS_FILE):
        return
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as handle:
        json.dump(
            sanitize_settings_payload(SETTINGS, DEFAULT_SESSIONS_FOLDER),
            handle,
            indent=2,
            ensure_ascii=False,
        )


for folder in (DATA_FOLDER, DEFAULT_SESSIONS_FOLDER, ARCHIVE_FOLDER):
    os.makedirs(folder, exist_ok=True)

_seed_file_if_missing(COLUMN_MAP_TEMPLATE_FILE, MAPPING_FILE)
_seed_settings_file_if_missing()


"""Session folder helpers"""

def _normalize_folder_path(path):
    if not path:
        return DEFAULT_SESSIONS_FOLDER
    normalized = os.path.abspath(path)
    return normalized


def ensure_directory(path):
    os.makedirs(path, exist_ok=True)
    return path


def get_sessions_folder():
    path = SETTINGS.get("sessions_folder") or DEFAULT_SESSIONS_FOLDER
    normalized = _normalize_folder_path(path)
    return ensure_directory(normalized)


def set_sessions_folder(path):
    normalized = _normalize_folder_path(path)
    ensure_directory(normalized)
    SETTINGS["sessions_folder"] = normalized
    return normalized



def _sanitize_path_component(value, fallback):
    raw = (value or '').strip()
    if not raw:
        return fallback
    sanitized = []
    for ch in raw:
        if ch in INVALID_PATH_CHARS:
            sanitized.append('_')
        else:
            sanitized.append(ch)
    sanitized_str = ''.join(sanitized)
    sanitized_str = sanitized_str.replace(os.sep, '_')
    if os.altsep:
        sanitized_str = sanitized_str.replace(os.altsep, '_')
    sanitized_str = sanitized_str.strip()
    sanitized_str = sanitized_str.rstrip('.')
    if sanitized_str in ('', '.', '..'):
        return fallback
    return sanitized_str


def resolve_session_directory(stage=None, center=None, *, create=False):
    base = get_sessions_folder()
    target = base
    if stage:
        stage_component = _sanitize_path_component(stage, 'Stage')
        target = os.path.join(target, stage_component)
        if create:
            ensure_directory(target)
    if center:
        center_component = _sanitize_path_component(center, 'Center')
        target = os.path.join(target, center_component)
        if create:
            ensure_directory(target)
    if not (stage or center) and create:
        ensure_directory(target)
    return target


def resolve_session_file_path(name, *, stage=None, center=None, ext='csv', create=False):
    ext = (ext or '').lstrip('.')
    ext = ext or 'csv'
    directory = resolve_session_directory(stage, center, create=create)
    filename = f"{name}.{ext}"
    return os.path.join(directory, filename)


def get_asset_path(name):
    return os.path.join(ASSETS_DIR, name)


def _build_temp_output_path(path):
    target = Path(path)
    return str(target.with_name(f"{target.stem}.tmp{target.suffix}"))


def save_json(path, payload, *, indent=2):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = _build_temp_output_path(path)
    try:
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=indent)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

def save_settings():
    save_json(SETTINGS_FILE, SETTINGS)




def bring_window_to_front(window):
    """Raise a toplevel window above its siblings and give it focus."""
    if window is None:
        return
    try:
        window.deiconify()
    except Exception:
        pass
    try:
        window.lift()
    except Exception:
        pass
    try:
        window.focus_force()
    except Exception:
        pass
    try:
        window.attributes('-topmost', True)
        window.after_idle(lambda: window.attributes('-topmost', False))
    except Exception:
        pass


def _ensure_app_dark_mode():
    global _DARK_MODE_APP_INITIALIZED
    if _DARK_MODE_APP_INITIALIZED or sys.platform != "win32":
        return
    try:
        uxtheme = ctypes.windll.uxtheme
    except Exception:
        _DARK_MODE_APP_INITIALIZED = True
        return
    try:
        allow_app = getattr(uxtheme, "AllowDarkModeForApp", None)
        if allow_app:
            allow_app.argtypes = [wintypes.BOOL]
            allow_app.restype = wintypes.BOOL
            allow_app(wintypes.BOOL(True))
        set_app_mode = getattr(uxtheme, "SetPreferredAppMode", None)
        if set_app_mode:
            set_app_mode.argtypes = [c_int]
            set_app_mode.restype = c_int
            # APPMODE_ALLOWDARK = 2
            set_app_mode(2)
        flush_themes = getattr(uxtheme, "FlushMenuThemes", None)
        if flush_themes:
            flush_themes()
    except Exception:
        pass
    _DARK_MODE_APP_INITIALIZED = True


def _get_window_handle(window):
    try:
        window.update_idletasks()
    except Exception:
        pass
    try:
        hwnd = window.winfo_id()
    except Exception:
        return None
    if not hwnd:
        return None
    try:
        get_ancestor = ctypes.windll.user32.GetAncestor
        get_ancestor.argtypes = [wintypes.HWND, c_uint]
        get_ancestor.restype = wintypes.HWND
        ancestor = get_ancestor(wintypes.HWND(hwnd), c_uint(2))
        if ancestor:
            hwnd = ancestor
    except Exception:
        try:
            parent = ctypes.windll.user32.GetParent(wintypes.HWND(hwnd))
            if parent:
                hwnd = parent
        except Exception:
            pass
    return int(hwnd) if hwnd else None



def _apply_dark_mode_to_hwnd(hwnd):
    applied = False
    hwnd = wintypes.HWND(hwnd)
    try:
        uxtheme = ctypes.windll.uxtheme
    except Exception:
        uxtheme = None
    if uxtheme:
        try:
            allow_window = getattr(uxtheme, "AllowDarkModeForWindow", None)
            if allow_window:
                allow_window.argtypes = [wintypes.HWND, wintypes.BOOL]
                allow_window.restype = wintypes.BOOL
                allow_window(hwnd, wintypes.BOOL(True))
        except Exception:
            pass
    try:
        dwm = ctypes.windll.dwmapi
    except Exception:
        dwm = None
    if dwm:
        try:
            dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, c_uint, c_void_p, c_uint]
        except AttributeError:
            pass
        value = c_int(1)
        size_value = ctypes.sizeof(value)
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1):
            try:
                result = dwm.DwmSetWindowAttribute(hwnd, c_uint(attribute), byref(value), size_value)
            except Exception:
                continue
            if result == 0:
                applied = True
                break
        caption_color = c_uint(0x001A1A1A)
        text_color = c_uint(0x00FFFFFF)
        size_color = ctypes.sizeof(caption_color)
        for attribute, data in ((DWMWA_CAPTION_COLOR, caption_color), (DWMWA_TEXT_COLOR, text_color)):
            try:
                result = dwm.DwmSetWindowAttribute(hwnd, c_uint(attribute), byref(data), size_color)
            except Exception:
                continue
            if result == 0:
                applied = True
    if not applied:
        try:
            user32 = ctypes.windll.user32
            set_attr = getattr(user32, "SetWindowCompositionAttribute")
        except Exception:
            return applied
        try:
            set_attr.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        except AttributeError:
            pass
        try:
            use_dark = wintypes.BOOL(True)
            data = WINDOWCOMPOSITIONATTRIBDATA(WCA_USEDARKMODECOLORS, ctypes.byref(use_dark), c_size_t(ctypes.sizeof(use_dark)))
            set_attr(hwnd, byref(data))
            applied = True
        except Exception:
            pass
    return applied



def set_dark_title_bar(window, *, attempts=12, interval_ms=90):
    '''Request dark mode for the native title bar, retrying while the window settles.'''
    if window is None or sys.platform != "win32":
        return
    _ensure_app_dark_mode()
    try:
        if not getattr(window, "_dark_title_bar_bound", False):
            def _remap(_event=None):
                set_dark_title_bar(window, attempts=attempts, interval_ms=interval_ms)
            window._dark_title_bar_bound = True
            window.bind("<Map>", _remap, add="+")
            window.bind("<FocusIn>", _remap, add="+")
    except Exception:
        pass
    try:
        job = getattr(window, "_dark_title_job", None)
        if job:
            window.after_cancel(job)
    except Exception:
        pass
    attempts = max(int(attempts), 1)

    def _attempt(remaining):
        hwnd = _get_window_handle(window)
        if hwnd is not None:
            _apply_dark_mode_to_hwnd(hwnd)
        remaining -= 1
        if remaining <= 0:
            return
        try:
            window._dark_title_job = window.after(interval_ms, lambda: _attempt(remaining))
        except Exception:
            pass

    try:
        window._dark_title_job = window.after(0, lambda: _attempt(attempts))
    except Exception:
        _attempt(attempts)


def ensure_initial_size(window, *, min_size=None, padding=(0, 0)):
    """Size a toplevel so its default geometry fits the current layout."""
    if window is None:
        return 0, 0
    window.update_idletasks()
    req_w = max(window.winfo_reqwidth(), window.winfo_width())
    req_h = max(window.winfo_reqheight(), window.winfo_height())
    pad_x, pad_y = padding if isinstance(padding, tuple) else (padding, padding)
    width = max(int(req_w + pad_x), 1)
    height = max(int(req_h + pad_y), 1)
    if min_size:
        min_w, min_h = min_size
        width = max(width, int(min_w))
        height = max(height, int(min_h))
    window.minsize(width, height)
    window.geometry(f"{width}x{height}")
    return width, height

def read_data(path, **kwargs):
    if path.lower().endswith(".xlsx"):
        df = pd.read_excel(path, dtype=str, **kwargs)
    else:
        df = pd.read_csv(path, dtype=str, **kwargs)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def write_data(df, path, **kwargs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = _build_temp_output_path(path)
    try:
        if path.lower().endswith(".xlsx"):
            df.to_excel(temp_path, index=False, **kwargs)
        else:
            df.to_csv(temp_path, index=False, **kwargs)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _clean_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _summary_bool_series(series):
    normalized = series.fillna("").astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "yes", "y"})


def compute_session_summary(df, column_map, restrictions):
    summary = {
        "total": 0,
        "attended": 0,
        "attendance_rate": "0%",
        "manual_additions": 0,
        "missing_exam": 0,
        "missing_hw": 0,
        "cancellations": 0,
    }
    if df is None or df.empty:
        return summary

    normalized_map = column_map or {}
    total = len(df.index)
    att_col = normalized_map.get("attendance", "attendance")
    notes_col = normalized_map.get("notes", "notes")
    card_id_col = normalized_map.get("card_id", "card_id")
    exam_col = normalized_map.get("exam", "exam")
    hw_col = normalized_map.get("homework", "homework")

    attended = 0
    if att_col in df.columns:
        attended = df[att_col].fillna("").astype(str).str.strip().str.lower().eq("attend").sum()

    summary["total"] = total
    summary["attended"] = int(attended)
    summary["attendance_rate"] = f"{(attended / total) * 100:.1f}%" if total else "0%"

    if restrictions.get("exam") and exam_col in df.columns:
        summary["missing_exam"] = int(sum(grade_missing_or_zero(value) for value in df[exam_col]))
    if restrictions.get("homework") and hw_col in df.columns:
        summary["missing_hw"] = int(sum(grade_missing_or_zero(value) for value in df[hw_col]))

    if SESSION_MANUAL_ADDED_COL in df.columns:
        manual_additions = int(_summary_bool_series(df[SESSION_MANUAL_ADDED_COL]).sum())
    else:
        notes_series = df[notes_col].fillna("").astype(str) if notes_col in df.columns else pd.Series([""] * total)
        card_series = df[card_id_col].fillna("").astype(str) if card_id_col in df.columns else pd.Series([""] * total)
        manual_mask = card_series.str.startswith("Unknown ") | notes_series.str.contains("Manually added|From diff Group", case=False, na=False)
        manual_additions = int(manual_mask.sum())
    summary["manual_additions"] = manual_additions

    if SESSION_LAST_ACTION_COL in df.columns:
        cancellations = df[SESSION_LAST_ACTION_COL].fillna("").astype(str).str.strip().str.lower().eq("canceled").sum()
    elif notes_col in df.columns:
        cancellations = df[notes_col].fillna("").astype(str).str.contains("Canceled", case=False, na=False).sum()
    else:
        cancellations = 0
    summary["cancellations"] = int(cancellations)
    return summary
