import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.sync_mop_report import (
    TargetAfterMeetingEntry,
    load_target_after_meeting_history,
    merge_target_after_meeting_entries,
    write_target_after_meeting_history,
)


class TargetAfterMeetingHistoryTest(unittest.TestCase):
    def test_keeps_closed_months_and_replaces_current_month_snapshot(self):
        historical = [
            TargetAfterMeetingEntry(date(2026, 9, 30), "Жуков Лев", 600),
            TargetAfterMeetingEntry(date(2026, 10, 1), "Жуков Лев", 300),
        ]
        live = [TargetAfterMeetingEntry(date(2026, 10, 2), "Жуков Лев", 420)]

        merged = merge_target_after_meeting_entries(historical, live, date(2026, 10, 8))

        self.assertEqual(merged, [
            TargetAfterMeetingEntry(date(2026, 9, 30), "Жуков Лев", 600),
            TargetAfterMeetingEntry(date(2026, 10, 2), "Жуков Лев", 420),
        ])

    def test_round_trips_history_file(self):
        entries = [TargetAfterMeetingEntry(date(2026, 9, 30), "Жуков Лев", 600)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            write_target_after_meeting_history(path, entries)

            self.assertEqual(load_target_after_meeting_history(path), entries)


if __name__ == "__main__":
    unittest.main()
