import unittest

from datetime import date

from scripts.sync_mop_report import (
    deal_is_high_priority,
    high_priority_called_deal_ids,
    high_priority_snapshot_mops,
)


def deal(deal_id: int, mop_name: str) -> dict[str, str]:
    return {"dealId": str(deal_id), "mopName": mop_name}


class HighPrioritySnapshotMopsTest(unittest.TestCase):
    def test_called_from_previous_uses_only_supplied_call_source(self) -> None:
        called_ids = high_priority_called_deal_ids(
            {"1", "2", "3", "4", "5"},
            {
                "1": [date(2026, 8, 26)],
                "4": [date(2026, 8, 25)],
            },
            "2026-08-25",
            "2026-08-26",
        )

        self.assertEqual(called_ids, ["1"])

    def test_overdue_starts_on_day_eight_and_excludes_fired_mops(self) -> None:
        allowed_stages = {"отложенный клиент"}
        excluded_mops = {"уволенный моп"}

        self.assertTrue(deal_is_high_priority(
            {"stageName": "Отложенный клиент", "mopName": "МОП", "daysWithoutCall": 8},
            8,
            allowed_stages,
            excluded_mops,
        ))
        self.assertFalse(deal_is_high_priority(
            {"stageName": "Отложенный клиент", "mopName": "МОП", "daysWithoutCall": 7},
            8,
            allowed_stages,
            excluded_mops,
        ))
        self.assertFalse(deal_is_high_priority(
            {"stageName": "Отложенный клиент", "mopName": "Уволенный МОП", "daysWithoutCall": 20},
            8,
            allowed_stages,
            excluded_mops,
        ))

    def test_counts_stop_days_and_daily_flow_by_manager(self) -> None:
        first_day = [deal(index, "МОП 1") for index in range(1, 12)]
        first_day.extend(deal(index, "МОП 2") for index in range(100, 105))
        second_day = [
            {**deal(index, "МОП 1"), "daysWithoutCall": index, "daysWithoutAttempt": index - 1}
            for index in range(1, 13)
        ]
        second_day.extend(deal(index, "МОП 2") for index in range(100, 111))
        snapshots = {
            "2026-08-24": {
                "deals": first_day,
                "previousDate": "",
                "calledFromPreviousDealIds": [],
                "flowedFromPreviousDealIds": [],
                "newOverdueDealIds": [row["dealId"] for row in first_day],
            },
            "2026-08-25": {
                "deals": second_day,
                "previousDate": "2026-08-24",
                "calledFromPreviousDealIds": ["1", "100"],
                "flowedFromPreviousDealIds": ["1", "2", "100"],
                "newOverdueDealIds": ["12", "105"],
            },
        }

        rows = high_priority_snapshot_mops(snapshots, "2026-08-25", 10)

        self.assertEqual(
            rows,
            [
                {
                    "mopName": "МОП 1",
                    "overdueCount": 12,
                    "calledFromPreviousCount": 1,
                    "flowedFromPreviousCount": 2,
                    "newOverdueCount": 1,
                    "maxDaysWithoutCall": 12,
                    "maxDaysWithoutAttempt": 11,
                    "isStop": True,
                    "stopDays": 2,
                },
                {
                    "mopName": "МОП 2",
                    "overdueCount": 11,
                    "calledFromPreviousCount": 1,
                    "flowedFromPreviousCount": 1,
                    "newOverdueCount": 1,
                    "maxDaysWithoutCall": None,
                    "maxDaysWithoutAttempt": None,
                    "isStop": True,
                    "stopDays": 1,
                },
            ],
        )

    def test_stop_requires_more_than_threshold(self) -> None:
        snapshots = {
            "2026-08-25": {
                "deals": [deal(index, "МОП") for index in range(10)],
                "previousDate": "",
                "calledFromPreviousDealIds": [],
                "flowedFromPreviousDealIds": [],
                "newOverdueDealIds": [],
            }
        }

        [row] = high_priority_snapshot_mops(snapshots, "2026-08-25", 10)

        self.assertFalse(row["isStop"])
        self.assertEqual(row["stopDays"], 0)


if __name__ == "__main__":
    unittest.main()
