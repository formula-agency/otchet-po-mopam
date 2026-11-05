from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from shared_plan_store import MOP_IDS_BY_NAME, MOP_NAMES  # noqa: E402
from sync_mop_report import DEFAULT_INCLUDED_MOPS, DEFAULT_MOP_NAMES_BY_ID  # noqa: E402


class NovemberPlanTest(unittest.TestCase):
    def test_sync_uses_current_mop_list_instead_of_stale_workflow_override(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/update-mop-report.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("MOP_INCLUDE_USERS:", workflow)

    def test_matches_approved_november_plan(self) -> None:
        store = json.loads(Path("manual-data/shared-plans.json").read_text(encoding="utf-8"))
        month = store["months"]["2026-11"]
        plans = {
            item["mopName"]: (
                item["airTimePlanSeconds"] // 60,
                item["meetingsPlan"],
                item["reservationsPlan"],
                item["approvedMortgagesPlan"],
                item["salesPlan"],
            )
            for item in month["plans"]
        }

        self.assertEqual(month["managerCount"], 13)
        self.assertEqual(
            plans,
            {
                "Тончу Ростислав": (400, 12, 9, 7, 2),
                "Погребинский Артем": (400, 12, 9, 7, 2),
                "Жуков Лев": (400, 12, 9, 7, 2),
                "Гавриленко Елена": (400, 12, 9, 7, 2),
                "Войнов Данил": (400, 12, 9, 7, 2),
                "Султанов Есен": (400, 12, 9, 7, 2),
                "Ядрышникова Кристина": (400, 12, 9, 7, 2),
                "Марина Данчук": (400, 12, 9, 7, 2),
                "Абоскалова Анна": (200, 8, 6, 4, 1),
                "Градцеева Елена": (400, 8, 6, 4, 1),
                "Аверкиев Дмитрий": (200, 8, 6, 4, 1),
                "Яловая Надежда": (200, 8, 6, 4, 1),
                "Полстянова Татьяна": (200, 8, 6, 4, 1),
            },
        )

    def test_new_mops_have_verified_bitrix_ids(self) -> None:
        expected = {
            "Градцеева Елена": "221",
            "Аверкиев Дмитрий": "222",
            "Полстянова Татьяна": "223",
            "Яловая Надежда": "224",
        }

        for name, user_id in expected.items():
            self.assertIn(name, DEFAULT_INCLUDED_MOPS)
            self.assertIn(name, MOP_NAMES)
            self.assertEqual(DEFAULT_MOP_NAMES_BY_ID[user_id], name)
            self.assertEqual(MOP_IDS_BY_NAME[name], user_id)


if __name__ == "__main__":
    unittest.main()
