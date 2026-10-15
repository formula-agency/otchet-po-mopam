from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.sync_mop_report import (
    MONGO_COMPLETED_CALL_CLASSIFICATIONS,
    MopReportData,
    MopSettings,
    ReportWindow,
    apply_manual_fact_adjustments,
    apply_mongo_call_aggregates,
    apply_mongo_deal_call_dates,
    apply_mongo_offer_counts_to_active_deals,
    apply_offer_call_details,
    apply_offer_deal_relations,
    apply_offer_lead_deal_links,
    apply_offer_recording_urls,
    apply_transcription_offer_fallbacks,
    build_mongo_offer_call_pipeline,
    build_offer_call_details,
    build_mongo_call_facts,
    build_mongo_call_aggregation_pipeline,
    build_mongo_target_after_meeting_pipeline,
    build_mongo_deal_call_pipeline,
    calculate_target_after_meeting_entries,
    key_for_mop_id,
    presentation_contains_offer,
    replace_target_after_meeting_facts,
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
        self.assertEqual(pipeline[2]["$addFields"]["duration"]["$cond"][2], "$duration")
        self.assertEqual(pipeline[3]["$lookup"]["from"], "call_analysis")
        self.assertEqual(
            pipeline[4]["$addFields"]["classification"]["$cond"][1],
            "Несостоявшийся разговор",
        )
        self.assertIn("targetCalls", pipeline[6]["$group"])
        self.assertIn("successfulTargetCalls", pipeline[6]["$group"])
        calls_condition = pipeline[6]["$group"]["calls"]["$sum"]["$cond"][0]
        self.assertEqual(
            calls_condition,
            {"$in": ["$classification", list(MONGO_COMPLETED_CALL_CLASSIFICATIONS)]},
        )
        self.assertNotIn("Автоответчик", MONGO_COMPLETED_CALL_CLASSIFICATIONS)
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
        self.assertIn("b24_deal_id", serialized)
        self.assertIn("deal_id", serialized)
        self.assertIn("bitrix_deal_id", serialized)
        self.assertIn("CRM_ENTITY_ID", serialized)
        self.assertIn("presentation", serialized)
        self.assertIn("transcriptionCandidateUids", serialized)
        self.assertIn("transcriptionCandidateCalls", serialized)
        self.assertIn("offerCallDates", serialized)
        self.assertNotIn("call_transcriptions", serialized)
        self.assertIn("offerCallsCount", serialized)
        self.assertIn("Сервисный звонок", serialized)
        self.assertIn("Нецелевой звонок", serialized)
        self.assertFalse(any("$out" in stage or "$merge" in stage for stage in pipeline))

    def test_target_after_meeting_pipeline_keeps_only_target_calls(self) -> None:
        tz = ZoneInfo("Asia/Yekaterinburg")
        start = datetime(2026, 10, 1, tzinfo=tz)
        end = datetime(2026, 10, 14, 23, 59, 59, tzinfo=tz)

        pipeline = build_mongo_target_after_meeting_pipeline(start, end)

        self.assertEqual(pipeline[0]["$match"]["call_date"], {"$gte": start, "$lte": end})
        self.assertEqual(pipeline[1]["$lookup"]["from"], "call_analysis")
        self.assertEqual(
            pipeline[3]["$match"]["classification"],
            {"$in": ["Целевой результативный", "Целевой нерезультативный", "Целевой звонок"]},
        )
        self.assertFalse(any("$out" in stage or "$merge" in stage for stage in pipeline))

    def test_offer_detection_uses_real_estate_presentations_only(self) -> None:
        self.assertTrue(presentation_contains_offer(
            "Менеджер предложила двухкомнатную квартиру площадью 54 кв. м "
            "по цене 7,2 млн рублей."
        ))
        self.assertTrue(presentation_contains_offer(
            "Презентовал апартамент площадью сорок два квадратных метра, "
            "стоимость шесть миллионов рублей."
        ))
        self.assertTrue(presentation_contains_offer(
            "Появилась евродвушка 38 квадратов по цене 4,89 млн со скидкой."
        ))
        self.assertFalse(presentation_contains_offer(
            "Менеджер предложила двухкомнатную квартиру и объяснила условия ипотеки."
        ))
        self.assertFalse(presentation_contains_offer(
            "Варианты квартир с ремонтом по субсидированным ставкам."
        ))
        self.assertFalse(presentation_contains_offer(
            "Я предлагаю нашу квартиру поставить в бронь, пусть студия в брони стоит."
        ))
        self.assertFalse(presentation_contains_offer(
            "Мы этот вариант ранее обсуждали: квартира 65 квадратов, евротрешка."
        ))
        self.assertFalse(presentation_contains_offer(
            "Клиент ищет квартиру площадью 50 квадратов с бюджетом 7 млн рублей."
        ))
        self.assertFalse(presentation_contains_offer(
            "Менеджер подобрал двухкомнатную квартиру площадью 52 квадрата. "
            "Первоначальный взнос 1 160 000 рублей, платеж 71 000 рублей."
        ))
        self.assertFalse(presentation_contains_offer(
            "Предположим, вот есть студия площадью 30 квадратов за 4 млн. "
            "Это просто как пример, а не реальное предложение."
        ))
        self.assertFalse(presentation_contains_offer(
            "Эту студию площадью 29 квадратов за 4,5 млн предлагать, честно, "
            "не очень бы хотелось."
        ))
        self.assertFalse(presentation_contains_offer(
            "Предложил квартиру с кухней 19 квадратов, цена пока неизвестна, "
            "но ипотечный платеж составит 50 тысяч рублей."
        ))
        self.assertFalse(presentation_contains_offer(
            "Предложил квартиру с кладовкой площадью 4,5 кв. м "
            "стоимостью 150 тысяч рублей."
        ))
        self.assertFalse(presentation_contains_offer(
            "Менеджер предложил обсудить квартиру площадью 50 квадратов. "
            + "Уточняли требования клиента. " * 40
            + "Другой объект стоит 7 млн рублей."
        ))
        self.assertFalse(presentation_contains_offer(
            "Менеджер предложил клиенту прислать документы и затем перезвонить."
        ))
        self.assertFalse(presentation_contains_offer(
            "Менеджер не предлагала квартиру во время разговора."
        ))
        self.assertFalse(presentation_contains_offer(
            "Менеджер подтвердил режим работы и готовность провести экскурсию по ЖК."
        ))

    def test_offer_pipeline_keeps_recording_and_manager_fields(self) -> None:
        tz = ZoneInfo("Asia/Yekaterinburg")
        window = ReportWindow(
            datetime(2026, 10, 1, tzinfo=tz),
            datetime(2026, 10, 14, tzinfo=tz),
        )

        pipeline = build_mongo_offer_call_pipeline(window, "Asia/Yekaterinburg")
        serialized = str(pipeline)

        self.assertIn("recording_url", serialized)
        self.assertIn("recordingUrl", serialized)
        self.assertIn("mopName", serialized)
        self.assertIn("dateTime", serialized)
        self.assertFalse(any("$out" in stage or "$merge" in stage for stage in pipeline))


class MongoCallAggregateTests(unittest.TestCase):
    def test_replaces_rounded_google_airtime_with_exact_templab_seconds(self) -> None:
        entries = calculate_target_after_meeting_entries(
            [
                {
                    "callUid": "call-before",
                    "callAt": datetime(2026, 10, 2, 9, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg")),
                    "durationSeconds": 50,
                    "dealId": "501",
                    "mopName": "Войнов Данил",
                },
                {
                    "callUid": "call-after",
                    "callAt": datetime(2026, 10, 2, 11, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg")),
                    "durationSeconds": 73,
                    "dealId": "501",
                    "mopName": "Войнов Данил",
                },
            ],
            [{"deal_id": "501", "meeting_complete_date": "02.10.2026 10:00"}],
            "Asia/Yekaterinburg",
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].seconds, 73)

        data = MopReportData()
        from scripts.sync_mop_report import add_fact

        add_fact(
            data,
            date(2026, 10, 2),
            "",
            "target_minutes_after_meeting_seconds",
            60,
            mop_name="Войнов Данил",
        )
        imported = replace_target_after_meeting_facts(
            data,
            entries,
            test_mop_settings(),
            date(2026, 10, 1),
            date(2026, 10, 14),
        )

        key = "name:войнов данил"
        self.assertEqual(imported, 73)
        self.assertEqual(
            data.daily_facts[date(2026, 10, 2)][key].target_minutes_after_meeting_seconds,
            73,
        )
        self.assertEqual(
            data.facts[week_start_for_date(date(2026, 10, 2))][key].target_minutes_after_meeting_seconds,
            73,
        )

    def test_applies_recording_urls_by_call_uuid(self) -> None:
        details = [
            {"callUid": "call-1", "recordingUrl": ""},
            {"callUid": "call-2", "recordingUrl": "https://existing.example/2.mp3"},
        ]

        applied = apply_offer_recording_urls(
            details,
            [
                {"call_uuid": "call-1", "audio_url_masked": "https://api.formula.templab.ru/storage/calls/1"},
                {"call_uuid": "call-1", "audio_url_masked": "https://records.example/1.mp3"},
                {"call_uuid": "call-2", "audio_url_masked": "https://records.example/new-2.mp3"},
            ],
        )

        self.assertEqual(applied, 1)
        self.assertEqual(details[0]["recordingUrl"], "https://records.example/1.mp3")
        self.assertEqual(details[1]["recordingUrl"], "https://existing.example/2.mp3")

    def test_builds_global_offer_details_from_analysis_and_transcription(self) -> None:
        rows = [
            {
                "callUid": "analysis-1",
                "day": "2026-10-13",
                "dateTime": "2026-10-13T10:30:00",
                "mopName": "Данил Войнов",
                "dealId": "501",
                "durationSeconds": 95,
                "recordingUrl": "https://records.example/call-1.mp3",
                "presentation": "Предложил квартиру 40 квадратов за 5 млн рублей.",
            },
            {
                "callUid": "transcript-1",
                "day": "2026-10-14",
                "dateTime": "2026-10-14T09:00:00",
                "mopName": "Попова Олеся",
                "dealId": "",
                "durationSeconds": 60,
                "presentation": "",
            },
        ]
        transcripts = [{
            "uuid": "transcript-1",
            "transcription": "Появилась евродвушка 38 квадратов по цене 4,9 млн.",
        }, {
            "uuid": "analysis-1",
            "transcription": "Полная расшифровка разговора без сокращения.\nВторая реплика.",
        }]

        details = build_offer_call_details(
            rows,
            transcripts,
            SimpleNamespace(bitrix_webhook_url="https://crm.example/rest/1/token/"),  # type: ignore[arg-type]
            test_mop_settings(),
        )
        data = MopReportData()
        apply_offer_call_details(data, details)

        self.assertEqual(len(details), 2)
        self.assertEqual(details[0]["selectionSource"], "transcription")
        self.assertEqual(details[1]["mopName"], "Войнов Данил")
        self.assertEqual(details[1]["dealUrl"], "https://crm.example/crm/deal/details/501/")
        self.assertEqual(
            details[1]["transcript"],
            "Полная расшифровка разговора без сокращения.\nВторая реплика.",
        )
        self.assertEqual(data.offer_calls_by_deal, {"501": 1})
        self.assertEqual(
            data.offer_call_counts_by_deal_date,
            {"501": {"2026-10-13": 1}},
        )

    def test_restores_offer_deal_links_from_templab_relations(self) -> None:
        details = [
            {"callUid": "call-1", "callExtId": "101", "dealId": "", "dealUrl": ""},
            {"callUid": "call-2", "callExtId": "102", "dealId": "", "dealUrl": ""},
            {"callUid": "call-3", "callExtId": "103", "dealId": "777", "dealUrl": "set"},
        ]
        relations = [
            {"call_uuid": "call-1", "process_deal_id": 501},
            {"call_ext_id": "102", "deal": {"id": "502"}},
            {"call_uuid": "call-3", "deal_id": "999"},
        ]

        applied = apply_offer_deal_relations(
            details,
            relations,
            SimpleNamespace(bitrix_webhook_url="https://crm.example/rest/1/token/"),  # type: ignore[arg-type]
        )

        self.assertEqual(applied, 2)
        self.assertEqual(details[0]["dealId"], "501")
        self.assertEqual(details[0]["dealUrl"], "https://crm.example/crm/deal/details/501/")
        self.assertEqual(details[1]["dealId"], "502")
        self.assertEqual(details[2]["dealId"], "777")

    def test_restores_offer_deal_link_from_bitrix_lead(self) -> None:
        details = [
            {"leadId": "91", "dealId": "", "dealUrl": ""},
            {"leadId": "92", "dealId": "777", "dealUrl": "set"},
        ]

        applied = apply_offer_lead_deal_links(
            details,
            {"91": "501", "92": "999"},
            SimpleNamespace(bitrix_webhook_url="https://crm.example/rest/1/token/"),  # type: ignore[arg-type]
        )

        self.assertEqual(applied, 1)
        self.assertEqual(details[0]["dealId"], "501")
        self.assertEqual(details[0]["dealUrl"], "https://crm.example/crm/deal/details/501/")
        self.assertEqual(details[1]["dealId"], "777")

    def test_transcription_fallback_counts_each_offer_call_once(self) -> None:
        rows = [
            {
                "_id": "501",
                "offerCallsCount": 1,
                "transcriptionCandidateUids": ["call-1", "call-2"],
                "transcriptionCandidateCalls": [
                    {"uuid": "call-1", "day": "2026-08-25"},
                    {"uuid": "call-2", "day": "2026-08-25"},
                ],
            },
            {
                "_id": "502",
                "offerCallsCount": 0,
                "transcriptionCandidateUids": ["call-3"],
            },
        ]
        documents = [
            {
                "uuid": "call-1",
                "transcription": "Предлагаю квартиру 38 квадратов по цене 4,89 млн.",
            },
            {
                "uuid": "call-1",
                "transcription": "Дубликат: предлагаю квартиру по той же цене.",
            },
            {
                "uuid": "call-2",
                "transcription": "Уточнили время следующего звонка.",
            },
            {
                "uuid": "call-3",
                "transcription": "Обсудили отправку документов без презентации.",
            },
        ]

        added = apply_transcription_offer_fallbacks(rows, documents)

        self.assertEqual(added, 1)
        self.assertEqual(rows[0]["offerCallsCount"], 2)
        self.assertEqual(rows[0]["offerCallDates"], ["2026-08-25"])
        self.assertEqual(rows[1]["offerCallsCount"], 0)

    def test_loads_distinct_call_dates_by_deal(self) -> None:
        data = MopReportData()

        linked_days = apply_mongo_deal_call_dates(
            data,
            [
                {
                    "_id": "501",
                    "attemptDates": ["2026-08-24", "2026-08-25", "2026-08-25"],
                    "successfulDates": ["2026-08-24"],
                    "offerCallsCount": 3,
                    "offerCallDates": ["2026-08-24", "2026-08-25", "2026-08-25"],
                },
                {"_id": "", "attemptDates": ["2026-08-25"]},
            ],
        )

        self.assertEqual(linked_days, 2)
        self.assertEqual(
            data.call_dates_by_deal["501"],
            [date(2026, 8, 24)],
        )
        self.assertEqual(
            data.call_attempt_dates_by_deal["501"],
            [date(2026, 8, 24), date(2026, 8, 25)],
        )
        self.assertEqual(data.offer_calls_by_deal["501"], 3)
        self.assertEqual(
            data.offer_call_counts_by_deal_date["501"],
            {"2026-08-24": 1, "2026-08-25": 2},
        )

    def test_applies_offer_counts_to_active_deals(self) -> None:
        payload = {"rows": [{"dealId": "501"}, {"dealId": "502"}]}

        apply_mongo_offer_counts_to_active_deals(
            payload,
            {"501": 4},
            {"501": {"2026-08-25": 2}},
        )

        self.assertEqual(payload["rows"][0]["offerCallsCount"], 4)
        self.assertEqual(payload["rows"][0]["offerCallsByDate"], {"2026-08-25": 2})
        self.assertEqual(payload["rows"][1]["offerCallsCount"], 0)
        self.assertEqual(payload["rows"][1]["offerCallsByDate"], {})

    def test_maps_formula_manager_name_to_existing_bitrix_identity(self) -> None:
        data = MopReportData()
        rows = [
            {
                "_id": {"day": "2026-08-19", "mopName": "Войнов Данил"},
                "calls": 2,
                "targetCalls": 1,
                "successfulTargetCalls": 1,
                "airSeconds": 65,
            }
        ]

        totals = apply_mongo_call_aggregates(data, rows, test_mop_settings())

        key = key_for_mop_id("199")
        sprint = week_start_for_date(date(2026, 8, 19))
        self.assertEqual(totals, (2, 65, 1))
        self.assertEqual(data.facts[sprint][key].calls, 2)
        self.assertEqual(data.facts[sprint][key].target_calls, 1)
        self.assertEqual(data.facts[sprint][key].successful_target_calls, 1)
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

        with TemporaryDirectory() as temporary_directory, patch.dict(
            "os.environ",
            {
                "MONGO_CALLS_REQUIRE_SERVER_READ_ONLY": "false",
                "MONGO_CALLS_AGGREGATION_TIMEOUT_MS": "120000",
                "MONGO_CALLS_FACT_CACHE_PATH": str(
                    Path(temporary_directory) / "mongo-call-facts.json"
                ),
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
