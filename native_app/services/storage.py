"""Persistence helpers for saved stream URLs."""

from __future__ import annotations

import json
from typing import TypedDict

from PySide6.QtCore import QSettings


class SavedUrl(TypedDict):
    url: str
    last_used_at: int


class UrlStore:
    KEY = "saved_urls_v1"
    MAX_SAVED_URLS = 20

    def __init__(self, settings: QSettings):
        self._settings = settings

    def load(self) -> list[SavedUrl]:
        raw = self._settings.value(self.KEY, "")
        if not isinstance(raw, str) or not raw.strip():
            return []

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if not isinstance(parsed, list):
            return []

        items: list[SavedUrl] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            last_used_at = int(item.get("last_used_at", 0) or 0)
            items.append({"url": url, "last_used_at": last_used_at})

        items.sort(key=lambda item: item["last_used_at"], reverse=True)
        return items[: self.MAX_SAVED_URLS]

    def save(self, saved_urls: list[SavedUrl]) -> None:
        serialized = json.dumps(saved_urls[: self.MAX_SAVED_URLS])
        self._settings.setValue(self.KEY, serialized)

    def mark_used(self, url: str, timestamp_ms: int) -> list[SavedUrl]:
        normalized = (url or "").strip()
        if not normalized:
            return self.load()

        saved_urls = self.load()
        existing = next((item for item in saved_urls if item["url"] == normalized), None)
        if existing:
            existing["last_used_at"] = timestamp_ms
        else:
            saved_urls.append({"url": normalized, "last_used_at": timestamp_ms})

        saved_urls.sort(key=lambda item: item["last_used_at"], reverse=True)
        next_saved = saved_urls[: self.MAX_SAVED_URLS]
        self.save(next_saved)
        return next_saved

