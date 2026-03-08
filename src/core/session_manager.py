"""Session management utilities."""
import os

import pandas as pd

from utils.helpers import (
    SETTINGS,
    SESSION_LAST_ACTION_COL,
    SESSION_MANUAL_ADDED_COL,
    get_sessions_folder,
    read_data,
    resolve_session_file_path,
    write_data,
)

class SessionManager:
    def __init__(self, name, params, column_map, data_df, session_path=None):
        self.params       = params or {}
        self.name         = name
        self.mapping      = column_map
        self.data_df      = data_df
        self.records      = []
        self._dirty       = False
        self.restrictions = SETTINGS["restrictions"]
        file_type = SETTINGS.get("file_type", "csv")
        ext = "xlsx" if file_type == "xlsx" else "csv"

        stage = self.params.get("stage")
        center = self.params.get("center")

        if session_path:
            computed_path = os.path.abspath(session_path)
        else:
            computed_path = resolve_session_file_path(
                name,
                stage=stage,
                center=center,
                ext=ext,
                create=True,
            )
            computed_path = os.path.abspath(computed_path)
            if not os.path.exists(computed_path):
                legacy_path = os.path.join(get_sessions_folder(), f"{name}.{ext}")
                if os.path.exists(legacy_path):
                    computed_path = os.path.abspath(legacy_path)

        self.session_path = computed_path
        directory = os.path.dirname(self.session_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        self._df = pd.DataFrame()
        if os.path.exists(self.session_path):
            df = read_data(self.session_path)
            self._df = df
        self._refresh_records()


    def add_record(self, rec):
        if "card_id" not in rec:
            raise ValueError("card_id is required")

        df = self._df.copy()
        card_col = self.mapping.get("card_id", "card_id")
        required_columns = {
            card_col,
            self.mapping.get("attendance", "attendance"),
            self.mapping.get("notes", "notes"),
            self.mapping.get("timestamp", "timestamp"),
            SESSION_MANUAL_ADDED_COL,
            SESSION_LAST_ACTION_COL,
        }
        for key in rec:
            required_columns.add(self.mapping.get(key, key))
        for column in required_columns:
            if column and column not in df.columns:
                df[column] = ""

        mask = df[card_col].fillna("").astype(str) == str(rec["card_id"])
        changed = False

        if mask.any():
            row_index = df.index[mask][0]
            for key, value in rec.items():
                column = self.mapping.get(key, key)
                if key == "timestamp" and not value:
                    continue
                new_value = "" if value is None else str(value)
                current_value = "" if pd.isna(df.at[row_index, column]) else str(df.at[row_index, column])
                if current_value != new_value:
                    df.at[row_index, column] = new_value
                    changed = True
        else:
            row = {column: "" for column in df.columns}
            for key, value in rec.items():
                column = self.mapping.get(key, key)
                row[column] = "" if value is None else str(value)
            df = pd.concat([df, pd.DataFrame([row], columns=df.columns)], ignore_index=True)
            changed = True

        if not changed:
            return False

        self._df = df
        self._dirty = True
        self._refresh_records()
        return True

    def get_dataframe(self, *, copy=True):
        return self._df.copy() if copy else self._df

    def has_pending_changes(self):
        return self._dirty

    def has_student_id_or_phone(self, student_id, phone):
        df = self._df
        sid_col = self.mapping.get("student_id", "student_id")
        phone_col = self.mapping.get("phone", "phone")
        student_text = "" if student_id is None else str(student_id)
        phone_text = "" if phone is None else str(phone)
        id_exists = student_text in df[sid_col].astype(str).values if sid_col in df.columns else False
        phone_exists = phone_text in df[phone_col].astype(str).values if phone_col in df.columns else False
        return id_exists, phone_exists

    def save(self, *, force=False):
        if not force and not self._dirty:
            return False
        write_data(self._df, self.session_path)
        self._dirty = False
        return True

    def _refresh_records(self):
        mapped_keys = ["card_id", "student_id", "name", "phone", "attendance", "notes", "timestamp"]
        if self.restrictions.get("exam"):
            mapped_keys.append("exam")
        if self.restrictions.get("homework"):
            mapped_keys.append("homework")
        self.records = []
        for _, row in self._df.iterrows():
            record = {}
            for key in mapped_keys:
                column = self.mapping.get(key, key)
                record[key] = row.get(column, "")
            self.records.append(record)
