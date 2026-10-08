import unittest
from collections import Counter
from datetime import date

from scripts import sync_mop_report as sync
from scripts.sync_marketing_sales import (
    MarketingMeeting,
    RegistrySale,
    classify_source,
    count_meetings,
    count_sales,
    meeting_cell_updates,
    registry_sales,
    sales_cell_updates,
    successful_meetings,
    unknown_cell_updates,
    unknown_meeting_cell_updates,
)


class MarketingSalesTest(unittest.TestCase):
    def test_registry_counts_each_completed_object_row(self):
        rows = [
            ["Сентябрь 2026", "", "Завершена", "", "", "", "", "", "Клиент", *([""] * 13), "https://crm.formula-agency.com/crm/deal/details/6147/"],
            ["Сентябрь 2026", "", "Завершена", "", "", "", "", "", "Клиент", *([""] * 13), "https://crm.formula-agency.com/crm/deal/details/6147/"],
            ["Сентябрь 2026", "", "На оформлении", "", "", "", "", "", "Клиент", *([""] * 13), "https://crm.formula-agency.com/crm/deal/details/6201/"],
        ]

        sales = registry_sales(rows, 2026)

        self.assertEqual([sale.deal_id for sale in sales], ["6147", "6147"])

    def test_classifies_known_utm_and_allowed_title_fallback(self):
        self.assertEqual(classify_source({"UTM_SOURCE": "leadit"}), "КЦ")
        self.assertEqual(classify_source({"UTM_SOURCE": "recommendation"}), "Рекомендация")
        self.assertEqual(classify_source({"TITLE": "Новый лид [Авито]"}), "Авито")
        self.assertEqual(classify_source({"TITLE": "Новый лид [Самоход]"}), "Самоход")
        self.assertEqual(classify_source({"UTM_SOURCE": "psk", "TITLE": "Арсен"}), "Не определено")

    def test_count_sales_keeps_duplicate_deal_rows(self):
        sales = [
            RegistrySale("2026-09", "6147", "Один клиент", 48),
            RegistrySale("2026-09", "6147", "Один клиент", 49),
            RegistrySale("2026-09", "", "Без ссылки", 50),
        ]

        counts, unknown = count_sales(sales, {"6147": {"UTM_SOURCE": "recommendation"}})

        self.assertEqual(counts[("2026-09", "Рекомендация")], 2)
        self.assertEqual(counts[("2026-09", "Не определено")], 1)
        self.assertEqual([sale.source_row for sale in unknown], [50])

    def test_builds_updates_only_for_existing_data_rows(self):
        counts = Counter({
            ("2026-09", "КЦ"): 7,
            ("2026-09", "Самоход"): 1,
            ("2026-09", "Рекомендация"): 6,
            ("2026-09", "Не определено"): 1,
        })

        data_updates = sales_cell_updates(
            [["Сентябрь", "КЦ"], ["Сентябрь", "Самоход"], ["Сентябрь", "Рекомендация"], ["", ""]],
            counts,
            2026,
        )
        unknown_updates = unknown_cell_updates([["Сентябрь"], [""]], counts, 2026)

        self.assertEqual(data_updates, [
            {"range": "'Данные'!F4", "values": [[7]]},
            {"range": "'Данные'!F5", "values": [[1]]},
            {"range": "'Данные'!F6", "values": [[6]]},
        ])
        self.assertEqual(unknown_updates, [
            {"range": "'Без меток'!C4", "values": [[1]]},
        ])

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
