import unittest
from datetime import date

from scripts.sync_mop_report import ActiveDealActivity, first_completed_meeting_dates_by_deal


class FirstCompletedMeetingDatesByDealTest(unittest.TestCase):
    def test_selects_first_completed_meeting_from_full_activity_history(self) -> None:
        events_by_deal = {
            "100": [
                ActiveDealActivity(date(2026, 6, 30), kind="meetings", completed=True),
                ActiveDealActivity(date(2026, 7, 2), kind="meetings", completed=True),
            ],
            "200": [
                ActiveDealActivity(date(2026, 7, 1), kind="calls", completed=True),
                ActiveDealActivity(date(2026, 7, 3), kind="meetings", completed=False),
                ActiveDealActivity(date(2026, 7, 4), kind="meetings", completed=True),
                ActiveDealActivity(date(2026, 7, 9), kind="meetings", completed=True),
            ],
            "300": [
                ActiveDealActivity(date(2026, 7, 5), kind="calls", completed=True),
            ],
        }

        result = first_completed_meeting_dates_by_deal(events_by_deal)

        self.assertEqual(
            result,
            {
                "100": date(2026, 6, 30),
                "200": date(2026, 7, 4),
            },
        )


if __name__ == "__main__":
    unittest.main()
