import unittest
from datetime import date

from scripts.sync_mop_report import MeetingLogEntry, first_successful_meetings_in_period


class FirstSuccessfulMeetingsInPeriodTest(unittest.TestCase):
    def test_keeps_only_first_successful_meeting_per_deal(self) -> None:
        entries = [
            MeetingLogEntry(date(2026, 6, 30), "100", "Mop One"),
            MeetingLogEntry(date(2026, 7, 2), "100", "Mop One"),
            MeetingLogEntry(date(2026, 7, 3), "200", "Mop Two"),
            MeetingLogEntry(date(2026, 7, 9), "200", "Mop Two"),
            MeetingLogEntry(date(2026, 7, 5), "", "Mop Three"),
            MeetingLogEntry(date(2026, 8, 1), "300", "Mop Three"),
        ]

        result = first_successful_meetings_in_period(
            entries,
            date(2026, 7, 1),
            date(2026, 7, 31),
        )

        self.assertEqual(result, [MeetingLogEntry(date(2026, 7, 3), "200", "Mop Two")])

    def test_prefers_named_entry_for_same_deal_and_date(self) -> None:
        entries = [
            MeetingLogEntry(date(2026, 7, 4), "400", ""),
            MeetingLogEntry(date(2026, 7, 4), "400", "Mop Four"),
        ]

        result = first_successful_meetings_in_period(
            entries,
            date(2026, 7, 1),
            date(2026, 7, 31),
        )

        self.assertEqual(result, [MeetingLogEntry(date(2026, 7, 4), "400", "Mop Four")])


if __name__ == "__main__":
    unittest.main()
