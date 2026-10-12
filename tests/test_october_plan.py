from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.sync_mop_report import DEFAULT_INCLUDED_MOPS, DEFAULT_MOP_NAMES_BY_ID


class OctoberPlanTest(unittest.TestCase):
    def test_matches_approved_october_plan(self) -> None:
        store = json.loads(Path("manual-data/shared-plans.json").read_text(encoding="utf-8"))
        plans = {
            item["mopName"]: (
                item["airTimePlanSeconds"] // 60,
                item["meetingsPlan"],
                item["reservationsPlan"],
                item["approvedMortgagesPlan"],
                item["salesPlan"],
            )
            for item in store["months"]["2026-10"]["plans"]
        }

        self.assertEqual(
            plans,
            {
                "Черткова Ирина": (400, 12, 9, 7, 1),
                "Попова Олеся": (400, 12, 9, 7, 2),
                "Тончу Ростислав": (400, 12, 9, 7, 2),
                "Погребинский Артем": (400, 12, 9, 7, 1),
                "Жуков Лев": (400, 12, 9, 7, 2),
                "Гавриленко Елена": (400, 12, 9, 7, 2),
                "Войнов Данил": (400, 12, 9, 7, 1),
                "Султанов Есен": (400, 12, 9, 7, 2),
                "Ядрышникова Кристина": (400, 12, 9, 7, 2),
                "Васильев Владимир": (150, 8, 6, 3, 1),
                "Марина Данчук": (400, 12, 9, 7, 2),
                "Абоскалова Анна": (150, 8, 6, 3, 1),
            },
        )

    def test_aboskalova_is_a_known_report_manager(self) -> None:
        self.assertIn("Абоскалова Анна", DEFAULT_INCLUDED_MOPS)
        self.assertEqual(DEFAULT_MOP_NAMES_BY_ID["216"], "Абоскалова Анна")


if __name__ == "__main__":
    unittest.main()
