import sys
import unittest
from datetime import date
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from import_vats_data import (  # noqa: E402
    CsvCallRecord,
    aggregate_csv_records,
    csv_call_is_completed,
    preferred_csv_sources,
    resolved_csv_source_kinds,
    SourceRange,
)
from import_megafon_calls import normalize_text  # noqa: E402


class CompletedCallsTest(unittest.TestCase):
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
