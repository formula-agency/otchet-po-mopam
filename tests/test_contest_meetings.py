import unittest
from datetime import date

from scripts.sync_mop_report import (
    MeetingLogEntry,
    successful_first_meeting_cycles_closed_in_period,
)


class SuccessfulFirstMeetingCyclesClosedInPeriodTest(unittest.TestCase):
    def test_counts_rescheduled_first_meeting_after_cancelled_attempt(self) -> None:
        entries = [
            MeetingLogEntry(date(2026, 7, 2), "100", "МОП 1", 1, date(2026, 7, 2), False),
            MeetingLogEntry(date(2026, 7, 5), "100", "МОП 1", 2, date(2026, 7, 5), True),
            MeetingLogEntry(date(2026, 6, 30), "200", "МОП 2", 1, date(2026, 6, 30), False),
            MeetingLogEntry(date(2026, 7, 4), "200", "МОП 2", 2, date(2026, 7, 4), True),
            MeetingLogEntry(date(2026, 7, 5), "300", "МОП 3", 1, date(2026, 7, 5), False),
            MeetingLogEntry(date(2026, 8, 1), "300", "МОП 3", 2, date(2026, 8, 1), True),
        ]

        result = successful_first_meeting_cycles_closed_in_period(
            entries,
            date(2026, 7, 1),
            date(2026, 7, 31),
        )

        self.assertEqual(
            result,
            [MeetingLogEntry(date(2026, 7, 5), "100", "МОП 1", 2, date(2026, 7, 5), True)],
        )

    def test_uses_closure_date_instead_of_meeting_start(self) -> None:
        entries = [
            MeetingLogEntry(date(2026, 6, 30), "100", "МОП 1", 1, date(2026, 7, 1), True),
        ]

        result = successful_first_meeting_cycles_closed_in_period(
            entries,
            date(2026, 7, 1),
            date(2026, 7, 31),
        )

        self.assertEqual(
            result,
            entries,
        )

    def test_prefers_named_mop_for_duplicate_success_on_same_date(self) -> None:
        entries = [
            MeetingLogEntry(date(2026, 7, 4), "200", "", 1, date(2026, 7, 4), True),
            MeetingLogEntry(date(2026, 7, 4), "200", "МОП 2", 1, date(2026, 7, 4), True),
        ]

        result = successful_first_meeting_cycles_closed_in_period(
            entries,
            date(2026, 7, 1),
            date(2026, 7, 31),
        )

        self.assertEqual(
            result,
            [MeetingLogEntry(date(2026, 7, 4), "200", "МОП 2", 1, date(2026, 7, 4), True)],
        )


if __name__ == "__main__":
    unittest.main()
