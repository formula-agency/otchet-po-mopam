import unittest
from collections import Counter
from datetime import date

from scripts import sync_mop_report as sync
from scripts.sync_marketing_meetings import (
    MarketingMeeting,
    classify_source,
    count_meetings,
    meeting_cell_updates,
    successful_meetings,
    unknown_meeting_cell_updates,
)


class MarketingMeetingsTest(unittest.TestCase):
    def test_classifies_known_utm_and_allowed_title_fallback(self):
        self.assertEqual(classify_source({"UTM_SOURCE": "leadit"}), "КЦ")
        self.assertEqual(classify_source({"UTM_SOURCE": "recommendation"}), "Рекомендация")
        self.assertEqual(classify_source({"TITLE": "Новый лид [Авито]"}), "Авито")
        self.assertEqual(classify_source({"TITLE": "Новый лид [Самоход]"}), "Самоход")
        self.assertEqual(classify_source({"UTM_SOURCE": "psk", "TITLE": "Арсен"}), "Не определено")

    def test_deduplicates_successful_meetings_by_deal(self):
        entries = [
            sync.MeetingLogEntry(date(2026, 9, 2), "100", "МОП", successful=True),
            sync.MeetingLogEntry(date(2026, 9, 8), "100", "МОП", successful=True),
            sync.MeetingLogEntry(date(2026, 9, 3), "101", "МОП", successful=False),
            sync.MeetingLogEntry(date(2026, 10, 1), "102", "МОП", successful=True),
        ]

        meetings, duplicates = successful_meetings(entries, {"2026-09"})

        self.assertEqual(meetings, [MarketingMeeting("2026-09", "100", date(2026, 9, 2))])
        self.assertEqual(duplicates, 1)

    def test_counts_meetings_by_event_month_regardless_of_deal_creation_date(self):
        meetings = [
            MarketingMeeting("2026-09", "100", date(2026, 9, 2)),
            MarketingMeeting("2026-09", "101", date(2026, 9, 3)),
            MarketingMeeting("2026-09", "102", date(2026, 9, 4)),
        ]
        deals = {
            "100": {"DATE_CREATE": "2026-08-20T10:00:00+05:00", "UTM_SOURCE": "leadit"},
            "101": {"DATE_CREATE": "2026-09-01T10:00:00+05:00", "TITLE": "Новый лид [Авито]"},
            "102": {"DATE_CREATE": "2026-02-28T10:00:00+05:00", "UTM_SOURCE": "selfwalk"},
        }

        counts = count_meetings(
            meetings,
            deals,
        )

        self.assertEqual(counts[("2026-09", "КЦ")], 1)
        self.assertEqual(counts[("2026-09", "Авито")], 1)
        self.assertEqual(counts[("2026-09", "Самоход")], 1)

    def test_builds_meeting_updates_for_data_and_unknown_tabs(self):
        counts = Counter({
            ("2026-09", "КЦ"): 31,
            ("2026-09", "Самоход"): 1,
            ("2026-09", "Не определено"): 1,
        })

        data_updates = meeting_cell_updates(
            [["Сентябрь", "КЦ"], ["Сентябрь", "Самоход"]],
            counts,
            2026,
        )
        unknown_updates = unknown_meeting_cell_updates([["Сентябрь"]], counts, 2026)

        self.assertEqual(data_updates, [
            {"range": "'Данные'!E4", "values": [[31]]},
            {"range": "'Данные'!E5", "values": [[1]]},
        ])
        self.assertEqual(unknown_updates, [
            {"range": "'Без меток'!B4", "values": [[1]]},
        ])


if __name__ == "__main__":
    unittest.main()
