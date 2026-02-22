from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from native_app.services.storage import UrlStore, mask_url_credentials


class FakeSettings:
    def __init__(self):
        self._values: dict[str, object] = {}

    def value(self, key: str, default_value: object = "") -> object:
        return self._values.get(key, default_value)

    def setValue(self, key: str, value: object) -> None:
        self._values[key] = value


class UrlStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = FakeSettings()
        self.store = UrlStore(self.settings)

    def test_load_migrates_legacy_fields(self) -> None:
        self.settings.setValue(
            UrlStore.KEY,
            json.dumps(
                [
                    {"url": "http://example-1", "last_used_at": 11},
                    {"url": "http://example-2", "lastUsedAt": 22},
                ]
            ),
        )

        loaded = self.store.load()

        self.assertEqual(2, len(loaded))
        self.assertEqual("http://example-2", loaded[0]["url"])
        self.assertEqual("", loaded[0]["label"])
        self.assertFalse(loaded[0]["pinned"])

    def test_mark_used_sorts_by_recency(self) -> None:
        self.store.mark_used("http://one", timestamp_ms=100)
        saved, blocked = self.store.mark_used("http://two", timestamp_ms=200)

        self.assertFalse(blocked)
        self.assertEqual(["http://two", "http://one"], [item["url"] for item in saved])

    def test_mark_used_prunes_oldest_unpinned_when_over_cap(self) -> None:
        items = []
        for idx in range(1, UrlStore.MAX_SAVED_URLS + 1):
            items.append(
                {
                    "url": f"http://camera-{idx}",
                    "label": "",
                    "pinned": idx == 1,
                    "last_used_at": idx,
                }
            )
        self.store.save(items)

        saved, blocked = self.store.mark_used("http://camera-new", timestamp_ms=999)

        self.assertFalse(blocked)
        urls = [item["url"] for item in saved]
        self.assertIn("http://camera-new", urls)
        self.assertIn("http://camera-1", urls)
        self.assertNotIn("http://camera-2", urls)
        self.assertEqual(UrlStore.MAX_SAVED_URLS, len(saved))

    def test_mark_used_blocks_when_all_existing_are_pinned(self) -> None:
        pinned_entries = []
        for idx in range(UrlStore.MAX_SAVED_URLS):
            pinned_entries.append(
                {
                    "url": f"http://pinned-{idx}",
                    "label": "",
                    "pinned": True,
                    "last_used_at": 1000 - idx,
                }
            )
        self.store.save(pinned_entries)

        saved, blocked = self.store.mark_used("http://new", timestamp_ms=2000)

        self.assertTrue(blocked)
        self.assertEqual(UrlStore.MAX_SAVED_URLS, len(saved))
        self.assertNotIn("http://new", [item["url"] for item in saved])

    def test_rename_pin_delete_and_clear_all(self) -> None:
        self.store.mark_used("http://stream", timestamp_ms=10)

        renamed = self.store.rename("http://stream", "Front Door")
        self.assertEqual("Front Door", renamed[0]["label"])

        pinned = self.store.set_pinned("http://stream", True)
        self.assertTrue(pinned[0]["pinned"])

        deleted = self.store.delete("http://stream")
        self.assertEqual([], deleted)

        self.store.mark_used("http://stream-2", timestamp_ms=20)
        self.store.clear_all()
        self.assertEqual([], self.store.load())

    def test_get_output_dir_uses_pictures_default_and_persists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            (home / "Pictures").mkdir(parents=True, exist_ok=True)

            with patch("native_app.services.storage.Path.home", return_value=home):
                output_dir = self.store.get_output_dir()
                self.assertEqual(home / "Pictures" / "MJPEG Capture Studio", output_dir)
                self.assertTrue(output_dir.exists())
                self.assertEqual(str(output_dir), self.settings.value(UrlStore.OUTPUT_DIR_KEY))

    def test_get_output_dir_falls_back_when_pictures_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)

            with patch("native_app.services.storage.Path.home", return_value=home):
                output_dir = self.store.get_output_dir()
                self.assertEqual(home / "MJPEG Capture Studio", output_dir)
                self.assertTrue(output_dir.exists())

    def test_set_output_dir_persists_custom_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            custom = Path(temp_dir) / "captures"
            configured = self.store.set_output_dir(custom)

        self.assertEqual(custom, configured)
        self.assertEqual(str(custom), self.settings.value(UrlStore.OUTPUT_DIR_KEY))


class MaskUrlCredentialsTests(unittest.TestCase):
    def test_masks_username_and_password(self) -> None:
        masked = mask_url_credentials("http://alice:secret@example.com/live")
        self.assertEqual("http://***:***@example.com/live", masked)

    def test_masks_username_only(self) -> None:
        masked = mask_url_credentials("http://alice@example.com/live")
        self.assertEqual("http://***@example.com/live", masked)

    def test_leaves_url_without_credentials_unchanged(self) -> None:
        url = "http://example.com/live"
        self.assertEqual(url, mask_url_credentials(url))

    def test_returns_original_on_malformed_url(self) -> None:
        malformed = "http://[::1"
        self.assertEqual(malformed, mask_url_credentials(malformed))


if __name__ == "__main__":
    unittest.main()
