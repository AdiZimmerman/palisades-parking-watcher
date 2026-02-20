#!/usr/bin/env python3
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import palisades_parking_watch as watcher


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


if __name__ == "__main__":
    unittest.main()
