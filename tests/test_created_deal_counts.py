from __future__ import annotations

import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.sync_mop_report import (
    MopReportData,
    ReportWindow,
    build_created_deal_counts,
    build_deal_metric_facts,
)


class CreatedDealCountsTest(unittest.TestCase):
    def test_november_closed_sales_are_attributed_to_october(self) -> None:
        timezone = ZoneInfo("Asia/Yekaterinburg")
        window = ReportWindow(
            datetime(2026, 10, 30, tzinfo=timezone),
            datetime(2026, 11, 3, 23, tzinfo=timezone),
        )
        settings = SimpleNamespace(
            report_timezone="Asia/Yekaterinburg",
            bitrix_approved_mortgage_field="UF_DEAL_MORTGAGE_APPROVED",
            bitrix_stage_field="STAGE_ID",
            bitrix_success_stage_ids=frozenset({"won"}),
        )
        mop_settings = SimpleNamespace(
            active_deal_category_names=("Льготная ипотека",),
            deal_date_field="DATE_CREATE",
            assigned_field="ASSIGNED_BY_ID",
            approved_mortgage_date_field="DATE_MODIFY",
        )
        records = [
            {
                "ID": deal_id,
                "CLOSEDATE": f"2026-11-0{day}T05:00:00+05:00",
                "STAGE_SEMANTIC_ID": "S",
                "ASSIGNED_BY_ID": "194",
            }
            for deal_id, day in (("5899", 2), ("6853", 2), ("6842", 3))
        ]
        data = MopReportData()

        with (
            patch("scripts.sync_mop_report.fetch_deal_category_names", return_value={"1": "Льготная ипотека"}),
            patch("scripts.sync_mop_report.fetch_deal_list", return_value=records),
            patch("scripts.sync_mop_report.fetch_day_deals", return_value=[]),
        ):
            build_deal_metric_facts(data, None, settings, mop_settings, window, [])

        october_sales = sum(metrics.sales for metrics in data.daily_facts[date(2026, 10, 30)].values())
        november_sales = sum(
            metrics.sales
            for day, by_mop in data.daily_facts.items()
            if day.month == 11
            for metrics in by_mop.values()
        )
        self.assertEqual(october_sales, 3)
        self.assertEqual(november_sales, 0)

    def test_counts_created_deals_including_closed_without_duplicates(self) -> None:
        timezone = ZoneInfo("Asia/Yekaterinburg")
        window = ReportWindow(
            datetime(2026, 11, 1, tzinfo=timezone),
            datetime(2026, 11, 5, 12, tzinfo=timezone),
        )
        settings = SimpleNamespace(report_timezone="Asia/Yekaterinburg")
        mop_settings = SimpleNamespace(
            active_deal_category_names=("Льготная ипотека",),
            include_users=frozenset({"войнов данил", "аверкиев дмитрий"}),
            exclude_users=frozenset(),
        )
        records = [
            {"ID": "1", "DATE_CREATE": "2026-11-02T11:00:00+05:00", "ASSIGNED_BY_ID": "199", "CLOSED": "Y"},
            {"ID": "1", "DATE_CREATE": "2026-11-02T11:00:00+05:00", "ASSIGNED_BY_ID": "199", "CLOSED": "Y"},
            {"ID": "2", "DATE_CREATE": "2026-11-02T12:00:00+05:00", "ASSIGNED_BY_ID": "222", "CLOSED": "N"},
            {"ID": "3", "DATE_CREATE": "2026-11-02T13:00:00+05:00", "ASSIGNED_BY_ID": "161", "CLOSED": "N"},
            {"ID": "4", "DATE_CREATE": "2026-10-31T23:00:00+05:00", "ASSIGNED_BY_ID": "199", "CLOSED": "N"},
        ]

        with (
            patch("scripts.sync_mop_report.fetch_deal_category_names", return_value={"1": "Льготная ипотека"}),
            patch("scripts.sync_mop_report.fetch_deal_list", return_value=records) as fetch_deals,
        ):
            result = build_created_deal_counts(None, settings, mop_settings, window)

        self.assertEqual(
            result,
            [
                {"date": "2026-11-02", "mopId": "199", "mopName": "Войнов Данил", "count": 1},
                {"date": "2026-11-02", "mopId": "222", "mopName": "Аверкиев Дмитрий", "count": 1},
            ],
        )
        self.assertEqual(fetch_deals.call_args.args[2]["CATEGORY_ID"], "1")
        self.assertNotIn("CLOSED", fetch_deals.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
