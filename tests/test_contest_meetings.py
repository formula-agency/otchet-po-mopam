import unittest
from datetime import date

from scripts.sync_mop_report import (
    MeetingLogEntry,
    deal_created_in_period,
    first_numbered_successful_meetings_in_period,
)


class FirstNumberedSuccessfulMeetingsInPeriodTest(unittest.TestCase):
    def test_keeps_only_successful_meetings_numbered_one(self) -> None:
        entries = [
            MeetingLogEntry(date(2026, 6, 30), "100", "МОП 1", 1),
            MeetingLogEntry(date(2026, 7, 2), "100", "МОП 1", 2),
            MeetingLogEntry(date(2026, 7, 4), "200", "МОП 2", 1),
            MeetingLogEntry(date(2026, 7, 9), "200", "МОП 2", 2),
            MeetingLogEntry(date(2026, 7, 5), "300", "МОП 3", None),
            MeetingLogEntry(date(2026, 8, 1), "400", "МОП 4", 1),
        ]

        result = first_numbered_successful_meetings_in_period(
            entries,
            date(2026, 7, 1),
            date(2026, 7, 31),
        )

        self.assertEqual(
            result,
            [MeetingLogEntry(date(2026, 7, 4), "200", "МОП 2", 1)],
        )

    def test_prefers_named_mop_for_duplicate_on_same_date(self) -> None:
        entries = [
            MeetingLogEntry(date(2026, 7, 4), "200", "", 1),
            MeetingLogEntry(date(2026, 7, 4), "200", "МОП 2", 1),
        ]

        result = first_numbered_successful_meetings_in_period(
            entries,
            date(2026, 7, 1),
            date(2026, 7, 31),
        )

        self.assertEqual(
            result,
            [MeetingLogEntry(date(2026, 7, 4), "200", "МОП 2", 1)],
        )

    def test_requires_deal_creation_inside_contest_period(self) -> None:
        period_start = date(2026, 7, 1)
        period_end = date(2026, 7, 31)

        self.assertTrue(
            deal_created_in_period(
                {"DATE_CREATE": "2026-07-15T12:00:00+05:00"},
                period_start,
                period_end,
                "Asia/Yekaterinburg",
            )
        )
        self.assertFalse(
            deal_created_in_period(
                {"DATE_CREATE": "2026-06-30T23:59:59+05:00"},
                period_start,
                period_end,
                "Asia/Yekaterinburg",
            )
        )


if __name__ == "__main__":
    unittest.main()
