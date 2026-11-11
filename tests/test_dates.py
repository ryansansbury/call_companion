"""Spoken dates resolve against the call's own day, and vague ones stay words."""
import unittest
from datetime import date

from engine import dates


class Dates(unittest.TestCase):
    def test_deal_dates(self):
        cases = [
            ("next Tuesday at ten", "2026-09-08", date(2026, 9, 15)),
            ("by Friday", "2026-09-15", date(2026, 9, 18)),
            ("by Thursday", "2026-09-15", date(2026, 9, 17)),
            ("by Wednesday the thirtieth", "2026-09-22", date(2026, 9, 30)),
            ("I'll decide by the thirtieth", "2026-09-22", date(2026, 9, 30)),
            ("a signature by October second", "2026-09-22", date(2026, 10, 2)),
            ("the week of October nineteenth", "2026-09-08", date(2026, 10, 19)),
            ("the week of the nineteenth", "2026-09-22", date(2026, 10, 19)),
            ("I'll get that to you today", "2026-09-10", date(2026, 9, 10)),
            ("December fifteenth", "2026-10-01", date(2026, 12, 15)),
            ("before the first of November", "2026-09-29", date(2026, 11, 1)),
            ("October 20", "2026-10-06", date(2026, 10, 20)),
            ("next quarter", "2026-09-22", None),
            ("soon", "2026-09-22", None),
        ]
        for phrase, day, want in cases:
            self.assertEqual(dates.resolve(phrase, day), want, phrase)


if __name__ == "__main__":
    unittest.main()
