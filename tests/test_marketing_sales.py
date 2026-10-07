import unittest
from collections import Counter

from scripts.sync_marketing_sales import (
    RegistrySale,
    classify_source,
    count_sales,
    registry_sales,
    sales_cell_updates,
    unknown_cell_updates,
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


if __name__ == "__main__":
    unittest.main()
