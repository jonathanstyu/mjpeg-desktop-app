"""Persistence helpers for saved stream URLs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, TypedDict
from urllib.parse import urlsplit, urlunsplit


class SettingsLike(Protocol):
    def value(self, key: str, default_value: Any = "") -> Any: ...

    def setValue(self, key: str, value: Any) -> None: ...


class SavedUrl(TypedDict):
    url: str
    label: str
    pinned: bool
    last_used_at: int


class UrlStore:
    KEY = "saved_urls_v1"
    OUTPUT_DIR_KEY = "output_dir_v1"
    MAX_SAVED_URLS = 20

    def __init__(self, settings: SettingsLike):
        self._settings = settings

    def default_output_dir(self) -> Path:
        home = Path.home()
        pictures_dir = home / "Pictures"
        if pictures_dir.exists() and pictures_dir.is_dir():
            return pictures_dir / "MJPEG Capture Studio"
        return home / "MJPEG Capture Studio"

    def get_output_dir(self) -> Path:
        raw = self._settings.value(self.OUTPUT_DIR_KEY, "")
        configured = str(raw or "").strip()

        if configured:
            try:
                return self._ensure_directory(Path(configured).expanduser())
            except (OSError, ValueError):
                pass

        default_dir = self._ensure_directory(self.default_output_dir())
        self._settings.setValue(self.OUTPUT_DIR_KEY, str(default_dir))
        return default_dir

    def set_output_dir(self, path: Path) -> Path:
        configured = str(path or "").strip()
        if not configured:
            raise ValueError("Output folder cannot be empty.")

        resolved = self._ensure_directory(Path(configured).expanduser())
        self._settings.setValue(self.OUTPUT_DIR_KEY, str(resolved))
        return resolved

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
            label = str(item.get("label", "")).strip()
            last_used_at = _parse_int(item.get("last_used_at", item.get("lastUsedAt", 0)), 0)
            pinned = _parse_bool(item.get("pinned", False))
            items.append({"url": url, "label": label, "pinned": pinned, "last_used_at": last_used_at})

        items.sort(key=lambda item: item["last_used_at"], reverse=True)
        return items[: self.MAX_SAVED_URLS]

    def save(self, saved_urls: list[SavedUrl]) -> None:
        serialized = json.dumps(saved_urls[: self.MAX_SAVED_URLS])
        self._settings.setValue(self.KEY, serialized)

    def mark_used(self, url: str, timestamp_ms: int) -> tuple[list[SavedUrl], bool]:
        normalized = (url or "").strip()
        if not normalized:
            return self.load(), False

        saved_urls = self.load()
        existing = next((item for item in saved_urls if item["url"] == normalized), None)
        created_new = existing is None

        if existing:
            existing["last_used_at"] = timestamp_ms
        else:
            saved_urls.append(
                {"url": normalized, "label": "", "pinned": False, "last_used_at": timestamp_ms}
            )

        saved_urls.sort(key=lambda item: item["last_used_at"], reverse=True)
        while len(saved_urls) > self.MAX_SAVED_URLS:
            remove_index = self._oldest_unpinned_index(saved_urls)
            if remove_index is None:
                break
            saved_urls.pop(remove_index)

        blocked = created_new and all(item["url"] != normalized for item in saved_urls)
        next_saved = saved_urls[: self.MAX_SAVED_URLS]
        self.save(next_saved)
        return next_saved, blocked

    def rename(self, url: str, label: str) -> list[SavedUrl]:
        normalized_url = (url or "").strip()
        next_label = (label or "").strip()
        if not normalized_url:
            return self.load()

        saved_urls = self.load()
        for entry in saved_urls:
            if entry["url"] == normalized_url:
                entry["label"] = next_label
                self.save(saved_urls)
                return saved_urls
        return saved_urls

    def set_pinned(self, url: str, pinned: bool) -> list[SavedUrl]:
        normalized_url = (url or "").strip()
        if not normalized_url:
            return self.load()

        saved_urls = self.load()
        for entry in saved_urls:
            if entry["url"] == normalized_url:
                entry["pinned"] = bool(pinned)
                self.save(saved_urls)
                return saved_urls
        return saved_urls

    def delete(self, url: str) -> list[SavedUrl]:
        normalized_url = (url or "").strip()
        if not normalized_url:
            return self.load()

        saved_urls = self.load()
        next_saved = [entry for entry in saved_urls if entry["url"] != normalized_url]
        if len(next_saved) != len(saved_urls):
            self.save(next_saved)
        return next_saved

    def clear_all(self) -> None:
        self._settings.setValue(self.KEY, "[]")

    def _oldest_unpinned_index(self, saved_urls: list[SavedUrl]) -> int | None:
        for index in range(len(saved_urls) - 1, -1, -1):
            if not saved_urls[index]["pinned"]:
                return index
        return None

    def _ensure_directory(self, path: Path) -> Path:
        normalized = str(path or "").strip()
        if not normalized:
            raise ValueError("Output folder path cannot be empty.")

        candidate = Path(normalized).expanduser()
        if candidate.exists() and not candidate.is_dir():
            raise ValueError(f"Output folder is not a directory: {candidate}")

        candidate.mkdir(parents=True, exist_ok=True)
        return candidate


def mask_url_credentials(url: str) -> str:
    normalized = (url or "").strip()
    if not normalized:
        return ""

    try:
        parsed = urlsplit(normalized)
    except ValueError:
        return normalized

    if "@" not in parsed.netloc:
        return normalized

    userinfo, hostinfo = parsed.netloc.rsplit("@", 1)
    if not userinfo:
        return normalized

    masked_userinfo = "***:***" if ":" in userinfo else "***"
    masked = parsed._replace(netloc=f"{masked_userinfo}@{hostinfo}")
    return urlunsplit(masked)


def _parse_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False
