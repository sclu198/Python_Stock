"""執行狀態：記住已經處理過的貼文，避免重複推播。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_REMEMBERED_IDS = 500


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"last_post_id": "", "seen_post_ids": [], "user_id": "", "last_run_at": ""}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"last_post_id": "", "seen_post_ids": [], "user_id": "", "last_run_at": ""}
        data.setdefault("last_post_id", "")
        data.setdefault("seen_post_ids", [])
        data.setdefault("user_id", "")
        data.setdefault("last_run_at", "")
        return data

    @property
    def last_post_id(self) -> str:
        return self._data.get("last_post_id", "")

    @property
    def user_id(self) -> str:
        return self._data.get("user_id", "")

    @user_id.setter
    def user_id(self, value: str) -> None:
        self._data["user_id"] = value

    def is_seen(self, post_id: str) -> bool:
        return post_id in set(self._data.get("seen_post_ids", []))

    def mark_seen(self, post_ids: list[str]) -> None:
        seen = self._data.get("seen_post_ids", [])
        for pid in post_ids:
            if pid not in seen:
                seen.append(pid)
        self._data["seen_post_ids"] = seen[-MAX_REMEMBERED_IDS:]
        numeric = [p for p in post_ids if p.isdigit()]
        if numeric:
            newest = max(numeric, key=int)
            current = self.last_post_id
            if not current.isdigit() or int(newest) > int(current):
                self._data["last_post_id"] = newest

    def set_last_run(self, iso_timestamp: str) -> None:
        self._data["last_run_at"] = iso_timestamp

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
