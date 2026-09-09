import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from import_vats_data import (  # noqa: E402
    CsvCallRecord,
    aggregate_csv_records,
    csv_call_is_completed,
    load_csv_sources,
    parse_csv_call_records,
    preferred_csv_sources,
    resolved_csv_source_kinds,
    SourceRange,
)
from import_megafon_calls import (  # noqa: E402
    canonical_mop_names,
    clear_existing_megafon_data,
    normalize_text,
)


class CompletedCallsTest(unittest.TestCase):
    def test_megafon_cleanup_preserves_other_source_markers(self) -> None:
        rows = [{"callsSource": "crm_calls_export", "airTimeSource": "crm_calls_export"}]

        cleaned = clear_existing_megafon_data(rows)

        self.assertEqual(cleaned[0]["callsSource"], "crm_calls_export")
        self.assertEqual(cleaned[0]["airTimeSource"], "crm_calls_export")

    def test_matches_two_part_names_in_reverse_order(self) -> None:
        name_map = canonical_mop_names({"filters": {"mopNames": ["Марина Данчук"]}})

        self.assertEqual(name_map[normalize_text("Данчук Марина")], "Марина Данчук")

    def test_reads_manager_summary_exports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vats_dir = Path(temp_dir) / "vats data"
            range_dir = vats_dir / "01.09-08.09"
            range_dir.mkdir(parents=True)
            calls_path = range_dir / "звонки.csv"
            air_path = range_dir / "эфир.csv"
            calls_path.write_text(
                "Менеджер;Звонки;Целевые;Результативные;Минуты\n"
                "Итого;10;4;2;30\n"
                "МОП 1;7;4;2;20\n",
                encoding="utf-8",
            )
            air_path.write_text(
                "Менеджер;Звонки;Целевые;Результативные;Минуты\n"
                "Итого;4;4;2;20\n"
                "МОП 1;4;4;2;20\n",
                encoding="utf-8",
            )

            call_records = parse_csv_call_records(calls_path, "calls", vats_dir)
            air_records = parse_csv_call_records(air_path, "air", vats_dir)

            self.assertEqual(len(call_records), 7)
            self.assertTrue(all(record.day == date(2026, 9, 8) for record in call_records))
            self.assertEqual(sum(csv_call_is_completed(record.classification) for record in call_records), 7)
            self.assertEqual(sum(record.classification.startswith("Целевой") for record in call_records), 4)
            self.assertEqual(sum(record.classification == "Целевой результативный" for record in call_records), 2)
            self.assertEqual(len(air_records), 1)
            self.assertEqual(air_records[0].duration_seconds, 20 * 60)

    def test_uses_only_latest_cumulative_summary_in_month(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vats_dir = Path(temp_dir) / "vats data"
            old_dir = vats_dir / "01.09-08.09"
            latest_dir = vats_dir / "01.09-09.09"
            old_dir.mkdir(parents=True)
            latest_dir.mkdir(parents=True)
            old_path = old_dir / "звонки.csv"
            latest_path = latest_dir / "звонки.csv"
            headers = "Менеджер;Звонки;Целевые;Результативные;Минуты\n"
            old_path.write_text(headers + "МОП 1;7;4;2;20\n", encoding="utf-8")
            latest_path.write_text(headers + "МОП 1;9;5;3;25\n", encoding="utf-8")

            records, ranges = load_csv_sources([old_path, latest_path], vats_dir)

            self.assertEqual(len(records), 9)
            self.assertEqual({record.path for record in records}, {latest_path})
            self.assertEqual([source_range.path for source_range in ranges], [latest_path])

    def test_detects_swapped_calls_and_air_exports(self) -> None:
        calls_path = Path("01.08-18.08/звонки.csv")
        air_path = Path("01.08-18.08/эфир.csv")
        records_by_path = {
            calls_path: [
                CsvCallRecord(calls_path, date(2026, 8, 17), "МОП 1", 60, "Целевой результативный", "calls"),
            ],
            air_path: [
                CsvCallRecord(air_path, date(2026, 8, 17), "МОП 1", 0, "Несостоявшийся разговор", "air"),
                CsvCallRecord(air_path, date(2026, 8, 17), "МОП 1", 60, "Целевой результативный", "air"),
            ],
        }

        resolved = resolved_csv_source_kinds(records_by_path)

        self.assertEqual(resolved[calls_path], "air")
        self.assertEqual(resolved[air_path], "calls")

    def test_keeps_correct_calls_and_air_exports(self) -> None:
        calls_path = Path("01.08-18.08/звонки.csv")
        air_path = Path("01.08-18.08/эфир.csv")
        records_by_path = {
            calls_path: [
                CsvCallRecord(calls_path, date(2026, 8, 17), "МОП 1", 0, "Несостоявшийся разговор", "calls"),
            ],
            air_path: [
                CsvCallRecord(air_path, date(2026, 8, 17), "МОП 1", 60, "Целевой результативный", "air"),
            ],
        }

        resolved = resolved_csv_source_kinds(records_by_path)

        self.assertEqual(resolved[calls_path], "calls")
        self.assertEqual(resolved[air_path], "air")

    def test_classifies_only_connected_calls_as_completed(self) -> None:
        completed = (
            "Сервисный звонок",
            "Нецелевой звонок",
            "Целевой нерезультативный",
            "Целевой результативный",
        )
        for classification in completed:
            with self.subTest(classification=classification):
                self.assertTrue(csv_call_is_completed(classification))

        for classification in ("Несостоявшийся разговор", "", "Автоответчик"):
            with self.subTest(classification=classification):
                self.assertFalse(csv_call_is_completed(classification))

    def test_preserves_attempts_and_counts_completed_calls_separately(self) -> None:
        path = Path("звонки.csv")
        classifications = (
            "Несостоявшийся разговор",
            "Сервисный звонок",
            "Нецелевой звонок",
            "Целевой нерезультативный",
            "Целевой результативный",
            "",
        )
        records = [
            CsvCallRecord(
                path=path,
                day=date(2026, 8, 11),
                employee="МОП 1",
                duration_seconds=0,
                classification=classification,
                source_kind="calls",
            )
            for classification in classifications
        ]
        ranges = [SourceRange(path=path, start=date(2026, 8, 1), end=date(2026, 8, 11))]

        rows, skipped, _used_paths, imported_calls, _imported_air = aggregate_csv_records(
            records,
            {normalize_text("МОП 1"): "МОП 1"},
            preferred_csv_sources(records, ranges),
        )

        self.assertEqual(skipped, {})
        self.assertEqual(imported_calls, 6)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["callsFact"], 6)
        self.assertEqual(rows[0]["crmCallsFact"], 6)
        self.assertEqual(rows[0]["completedCallsFact"], 4)
        self.assertEqual(rows[0]["targetCallsFact"], 2)
        self.assertEqual(rows[0]["targetSuccessfulCallsFact"], 1)


if __name__ == "__main__":
    unittest.main()
