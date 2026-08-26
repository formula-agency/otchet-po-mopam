from __future__ import annotations

import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.sync_mop_report import (
    MopReportData,
    MopSettings,
    ReportWindow,
    apply_manual_fact_adjustments,
    apply_mongo_call_aggregates,
    apply_mongo_deal_call_dates,
    build_mongo_call_facts,
    build_mongo_call_aggregation_pipeline,
    build_mongo_deal_call_pipeline,
    key_for_mop_id,
    week_start_for_date,
)


def test_mop_settings() -> MopSettings:
    include_names = ("Войнов Данил", "Попова Олеся")
    return MopSettings(
        plan_sheet_id="",
        plan_sheet_name="Планы МОП",
        plan_sheet_gid="",
        plan_month="",
        plan_required=False,
        dashboard_dir=Path("dashboard"),
        deal_date_field="DATE_CREATE",
        approved_mortgage_date_field="DATE_MODIFY",
        assigned_field="ASSIGNED_BY_ID",
        unknown_mop_name="Без ответственного",
        include_user_labels=include_names,
        include_users=frozenset(name.lower() for name in include_names),
        exclude_users=frozenset(),
        call_min_duration_seconds=5,
        active_deal_category_names=("Льготная ипотека",),
    )


class MongoCallPipelineTests(unittest.TestCase):
    def test_pipeline_filters_window_converts_timezone_and_deduplicates(self) -> None:
        timezone_name = "Asia/Yekaterinburg"
        tz = ZoneInfo(timezone_name)
        window = ReportWindow(
            datetime(2026, 8, 1, tzinfo=tz),
            datetime(2026, 8, 19, 10, 0, tzinfo=tz),
        )

        pipeline = build_mongo_call_aggregation_pipeline(window, timezone_name, 5)

        self.assertEqual(
            pipeline[0]["$match"]["call_date"],
            {"$gte": window.start, "$lte": window.end},
        )
        self.assertEqual(
            pipeline[1]["$project"]["day"]["$dateToString"]["timezone"],
            timezone_name,
        )
        self.assertEqual(pipeline[2]["$match"]["duration"], {"$gte": 5})
        self.assertEqual(pipeline[3]["$group"]["_id"], "$dedupeKey")
        self.assertFalse(any("$out" in stage or "$merge" in stage for stage in pipeline))

    def test_deal_pipeline_supports_direct_and_crm_entity_ids(self) -> None:
        timezone_name = "Asia/Yekaterinburg"
        tz = ZoneInfo(timezone_name)
        window = ReportWindow(
            datetime(2026, 8, 1, tzinfo=tz),
            datetime(2026, 8, 26, 10, 0, tzinfo=tz),
        )

        pipeline = build_mongo_deal_call_pipeline(window, timezone_name)

        serialized = str(pipeline)
        self.assertIn("deal_id", serialized)
        self.assertIn("bitrix_deal_id", serialized)
        self.assertIn("CRM_ENTITY_ID", serialized)
        self.assertFalse(any("$out" in stage or "$merge" in stage for stage in pipeline))


class MongoCallAggregateTests(unittest.TestCase):
    def test_loads_distinct_call_dates_by_deal(self) -> None:
        data = MopReportData()

        linked_days = apply_mongo_deal_call_dates(
            data,
            [
                {"_id": "501", "dates": ["2026-08-24", "2026-08-25", "2026-08-25"]},
                {"_id": "", "dates": ["2026-08-25"]},
            ],
        )

        self.assertEqual(linked_days, 2)
        self.assertEqual(
            data.call_dates_by_deal["501"],
            [date(2026, 8, 24), date(2026, 8, 25)],
        )
    def test_maps_formula_manager_name_to_existing_bitrix_identity(self) -> None:
        data = MopReportData()
        rows = [
            {
                "_id": {"day": "2026-08-19", "mopName": "Войнов Данил"},
                "calls": 2,
                "airSeconds": 65,
            }
        ]

        totals = apply_mongo_call_aggregates(data, rows, test_mop_settings())

        key = key_for_mop_id("199")
        sprint = week_start_for_date(date(2026, 8, 19))
        self.assertEqual(totals, (2, 65, 1))
        self.assertEqual(data.facts[sprint][key].calls, 2)
        self.assertEqual(data.facts[sprint][key].air_seconds, 65)
        self.assertEqual(data.daily_facts[date(2026, 8, 19)][key].calls, 2)
        self.assertEqual(data.identities[key].mop_name, "Войнов Данил")

    def test_ignores_managers_outside_report_filter(self) -> None:
        data = MopReportData()
        rows = [
            {
                "_id": {"day": "2026-08-19", "mopName": "Другой Менеджер"},
                "calls": 3,
                "airSeconds": 90,
            }
        ]

        totals = apply_mongo_call_aggregates(data, rows, test_mop_settings())

        self.assertEqual(totals, (0, 0, 0))
        self.assertEqual(dict(data.facts), {})


class FakeMongoCollection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.pipeline = None

    def aggregate(self, pipeline, **kwargs):
        self.pipeline = pipeline
        return list(self.rows)


class FakeMongoReader:
    data_sources = {"calls_collection": "mongo_calls"}
    server_read_only = False

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.mongo_collection = FakeMongoCollection(rows)

    def collection(self, name: str) -> FakeMongoCollection:
        if name != "mongo_calls":
            raise AssertionError(name)
        return self.mongo_collection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class MongoCallSourceTests(unittest.TestCase):
    def test_builds_facts_through_client_read_only_api_with_privileged_server_role(self) -> None:
        tz = ZoneInfo("Asia/Yekaterinburg")
        window = ReportWindow(
            datetime(2026, 8, 1, tzinfo=tz),
            datetime(2026, 8, 19, 10, 0, tzinfo=tz),
        )
        reader = FakeMongoReader(
            [
                {
                    "_id": {"day": "2026-08-19", "mopName": "Войнов Данил"},
                    "calls": 2,
                    "airSeconds": 65,
                }
            ]
        )
        data = MopReportData()

        with patch.dict(
            "os.environ",
            {
                "MONGO_CALLS_REQUIRE_SERVER_READ_ONLY": "false",
                "MONGO_CALLS_AGGREGATION_TIMEOUT_MS": "120000",
            },
            clear=False,
        ), patch(
            "scripts.sync_mop_report.FormulaMongoReader.from_env",
            return_value=reader,
        ) as from_env:
            loaded = build_mongo_call_facts(
                data,
                SimpleNamespace(report_timezone="Asia/Yekaterinburg"),  # type: ignore[arg-type]
                test_mop_settings(),
                window,
            )

        self.assertTrue(loaded)
        from_env.assert_called_once_with(None, require_server_read_only=False)
        self.assertEqual(data.call_source, "mongodb:formula/mongo_calls")
        self.assertFalse(data.call_source_server_read_only)
        self.assertIsNotNone(reader.mongo_collection.pipeline)

    def test_mongo_source_does_not_receive_legacy_manual_call_adjustments(self) -> None:
        data = MopReportData()
        tz = ZoneInfo("Asia/Yekaterinburg")
        window = ReportWindow(
            datetime(2026, 6, 1, tzinfo=tz),
            datetime(2026, 6, 30, 23, 59, tzinfo=tz),
        )

        apply_manual_fact_adjustments(data, window, include_call_metrics=False)

        self.assertEqual(dict(data.facts), {})


if __name__ == "__main__":
    unittest.main()
