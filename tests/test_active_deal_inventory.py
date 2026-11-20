from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.sync_mop_report import MopReportData, ReportWindow, build_active_deals_payload


class ActiveDealInventoryTest(unittest.TestCase):
    def test_counts_open_pipeline_deals_before_report_start_and_outside_mop_roster(self) -> None:
        timezone = ZoneInfo("Asia/Yekaterinburg")
        window = ReportWindow(
            datetime(2026, 3, 1, tzinfo=timezone),
            datetime(2026, 11, 20, 12, tzinfo=timezone),
        )
        settings = SimpleNamespace(
            report_timezone="Asia/Yekaterinburg",
            bitrix_approved_mortgage_field="UF_APPROVED",
            bitrix_webhook_url="https://crm.example.test/rest/1/key/",
        )
        mop_settings = SimpleNamespace(
            active_deal_category_names=("Льготная ипотека",),
            assigned_field="ASSIGNED_BY_ID",
            approved_mortgage_date_field="DATE_MODIFY",
            include_users=frozenset({"ковалев иван"}),
            include_user_labels=("Ковалев Иван",),
            exclude_users=frozenset(),
            unknown_mop_name="Без ответственного",
        )
        records = [
            {"ID": "1", "DATE_CREATE": "2025-12-12T10:00:00+05:00", "ASSIGNED_BY_ID": "229"},
            {"ID": "1", "DATE_CREATE": "2025-12-12T10:00:00+05:00", "ASSIGNED_BY_ID": "229"},
            {"ID": "2", "DATE_CREATE": "2026-11-03T10:00:00+05:00", "ASSIGNED_BY_ID": "229"},
            {"ID": "3", "DATE_CREATE": "2026-11-04T10:00:00+05:00", "ASSIGNED_BY_ID": "117"},
            {"ID": "4", "DATE_CREATE": "2026-11-05T10:00:00+05:00", "ASSIGNED_BY_ID": "153"},
        ]

        with (
            patch("scripts.sync_mop_report.fetch_deal_category_names", return_value={"1": "Льготная ипотека"}),
            patch("scripts.sync_mop_report.fetch_deal_list", return_value=records) as fetch_deals,
            patch("scripts.sync_mop_report.fetch_bitrix_user_names", return_value={
                "229": "Ковалев Иван", "117": "Баринова Дарья", "153": "Грибанов Кирилл",
            }),
            patch("scripts.sync_mop_report.fetch_deal_stage_names", return_value={}),
            patch("scripts.sync_mop_report.fetch_deal_activity_events_batch", return_value={}),
        ):
            payload = build_active_deals_payload(
                MopReportData(), None, None, settings, mop_settings, window, []
            )

        self.assertEqual(fetch_deals.call_args.args[2]["CATEGORY_ID"], "1")
        self.assertEqual(fetch_deals.call_args.args[2]["CLOSED"], "N")
        self.assertEqual({row["dealId"] for row in payload["rows"]}, {"1", "2"})
        self.assertEqual(payload["allOpenDealCountsByCreateDate"], [
            {"date": "2025-12-12", "count": 1},
            {"date": "2026-11-03", "count": 1},
            {"date": "2026-11-04", "count": 1},
            {"date": "2026-11-05", "count": 1},
        ])


if __name__ == "__main__":
    unittest.main()
