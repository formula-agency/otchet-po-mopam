from __future__ import annotations

import unittest
import sys
from datetime import date
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from import_megafon_calls import empty_metric_row  # noqa: E402
from shared_plan_store import merge_shared_daily_plan_rows, merge_shared_plan_rows  # noqa: E402


class SharedPlanMergeTest(unittest.TestCase):
    def test_merges_duplicate_mop_rows_before_applying_plan(self) -> None:
        fact_by_id = empty_metric_row(
            date(2026, 10, 1),
            mop_name="Жуков Лев",
            mop_id="194",
            manual_aggregate=False,
        )
        fact_by_id.update({"meetingsFact": 2, "airTimeFactSeconds": 120})
        fact_by_name = empty_metric_row(
            date(2026, 10, 1),
            mop_name="Жуков Лев",
            mop_id="",
            manual_aggregate=False,
        )
        fact_by_name.update({"reservationsFact": 1, "airTimeFactSeconds": 60})
        shared_plan = empty_metric_row(
            date(2026, 10, 1),
            mop_name="Жуков Лев",
            mop_id="194",
            manual_aggregate=False,
        )
        shared_plan.update({
            "salesPlan": 1,
            "meetingsPlan": 3,
            "reservationsPlan": 2,
            "approvedMortgagesPlan": 1,
            "airTimePlanSeconds": 6000,
            "planSource": "shared_upload",
            "sharedPlanOnlyRow": True,
        })
        payload = {"baseRows": [fact_by_id, fact_by_name]}

        rows = merge_shared_plan_rows(payload, [shared_plan])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mopId"], "194")
        self.assertEqual(rows[0]["meetingsFact"], 2)
        self.assertEqual(rows[0]["reservationsFact"], 1)
        self.assertEqual(rows[0]["airTimeFactSeconds"], 180)
        self.assertEqual(rows[0]["meetingsPlan"], 3)
        self.assertEqual(rows[0]["airTimePlanSeconds"], 6000)

    def test_merges_duplicate_daily_fact_rows(self) -> None:
        first = empty_metric_row(
            date(2026, 10, 1),
            mop_name="Жуков Лев",
            mop_id="194",
            manual_aggregate=False,
        )
        first.update({"date": "2026-10-01", "meetingsFact": 1})
        second = empty_metric_row(
            date(2026, 10, 1),
            mop_name="Жуков Лев",
            mop_id="",
            manual_aggregate=False,
        )
        second.update({"date": "2026-10-01", "meetingsFact": 2})
        payload = {"baseRows": [], "dailyRows": [first, second]}

        rows = merge_shared_daily_plan_rows(payload)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["meetingsFact"], 3)


if __name__ == "__main__":
    unittest.main()
