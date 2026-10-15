import unittest
from datetime import date

from scripts.sync_mop_report import MeetingLogEntry, meeting_fact_event_date


class MeetingFactDateTest(unittest.TestCase):
    def test_uses_successful_close_date_for_crm_month(self):
        entry = MeetingLogEntry(
            meeting_date=date(2026, 8, 31),
            deal_id="6122",
            mop_name="Ядрышникова Кристина",
            closed_date=date(2026, 9, 11),
        )

        self.assertEqual(meeting_fact_event_date(entry), date(2026, 9, 11))

    def test_falls_back_to_meeting_start_when_close_date_is_missing(self):
        entry = MeetingLogEntry(
            meeting_date=date(2026, 9, 5),
            deal_id="501",
            mop_name="Войнов Данил",
        )

        self.assertEqual(meeting_fact_event_date(entry), date(2026, 9, 5))


if __name__ == "__main__":
    unittest.main()
