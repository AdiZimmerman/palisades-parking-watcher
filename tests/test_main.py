#!/usr/bin/env python3
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
import main as watcher


class CalendarStyleTests(unittest.TestCase):
    def test_green_means_available(self) -> None:
        is_available, reason = watcher.classify_day_style(
            "background-color: rgba(49, 200, 25, 0.2); color: rgb(0, 0, 0);",
            "false",
        )
        self.assertTrue(is_available)
        self.assertIn("available", reason.lower())

    def test_pink_means_sold_out(self) -> None:
        is_available, reason = watcher.classify_day_style(
            "background-color: rgb(247, 205, 212); color: rgb(0, 0, 0);",
            "false",
        )
        self.assertFalse(is_available)
        self.assertIn("sold out", reason.lower())

    def test_disabled_means_not_available(self) -> None:
        is_available, reason = watcher.classify_day_style(None, "true")
        self.assertFalse(is_available)
        self.assertIn("disabled", reason.lower())


class HelperTests(unittest.TestCase):
    def test_target_label(self) -> None:
        d = watcher.parse_target_date("2026-02-28")
        self.assertEqual(watcher.target_label(d), "Saturday, February 28, 2026")

    def test_month_name_to_number(self) -> None:
        self.assertEqual(watcher.month_name_to_number("February"), 2)
        self.assertEqual(watcher.month_name_to_number("Mar"), 3)


class RetryBehaviorTests(unittest.TestCase):
    @mock.patch.object(watcher.time, "sleep")
    @mock.patch.object(watcher, "fetch_calendar_status_once")
    def test_retries_then_succeeds(self, mock_fetch: mock.Mock, mock_sleep: mock.Mock) -> None:
        target_date = watcher.parse_target_date("2026-02-28")
        mock_fetch.side_effect = [
            RuntimeError("Playwright timeout: slow page"),
            (True, "ok", "snapshot"),
        ]

        result = watcher.fetch_calendar_status(target_date, "ALPINE")

        self.assertEqual(result, (True, "ok", "snapshot"))
        self.assertEqual(mock_fetch.call_count, 2)
        mock_sleep.assert_called_once_with(watcher.RETRYABLE_BACKOFF_SECONDS)

    @mock.patch.object(watcher.time, "sleep")
    @mock.patch.object(watcher, "fetch_calendar_status_once")
    def test_raises_after_max_attempts(self, mock_fetch: mock.Mock, mock_sleep: mock.Mock) -> None:
        target_date = watcher.parse_target_date("2026-02-28")
        mock_fetch.side_effect = RuntimeError("Target day cell not found")

        with self.assertRaises(RuntimeError) as exc:
            watcher.fetch_calendar_status(target_date, "ALPINE")

        self.assertIn("after 3 attempts", str(exc.exception))
        self.assertEqual(mock_fetch.call_count, watcher.MAX_FETCH_ATTEMPTS)
        self.assertEqual(mock_sleep.call_count, watcher.MAX_FETCH_ATTEMPTS - 1)

    @mock.patch.object(watcher.time, "sleep")
    @mock.patch.object(watcher, "fetch_calendar_status_once")
    def test_does_not_retry_if_playwright_missing(
        self, mock_fetch: mock.Mock, mock_sleep: mock.Mock
    ) -> None:
        target_date = watcher.parse_target_date("2026-02-28")
        mock_fetch.side_effect = RuntimeError("playwright is not installed")

        with self.assertRaises(RuntimeError) as exc:
            watcher.fetch_calendar_status(target_date, "ALPINE")

        self.assertIn("playwright is not installed", str(exc.exception))
        self.assertEqual(mock_fetch.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
