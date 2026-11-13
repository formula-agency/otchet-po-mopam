from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from shared_plan_store import MOP_IDS_BY_NAME, MOP_NAMES  # noqa: E402
from sync_mop_report import (  # noqa: E402
    DEFAULT_INCLUDED_MOPS,
    DEFAULT_MOP_NAMES_BY_ID,
    fetch_bitrix_mop_roster,
)


class MopRosterTest(unittest.TestCase):
    def test_new_sales_managers_are_configured_consistently(self) -> None:
        expected = {
            "Овчинников Станислав": "225",
            "Фабрициус Татьяна": "226",
            "Устинова Ольга": "227",
            "Григорович Елена": "228",
        }
        for name, user_id in expected.items():
            self.assertIn(name, DEFAULT_INCLUDED_MOPS)
            self.assertIn(name, MOP_NAMES)
            self.assertEqual(DEFAULT_MOP_NAMES_BY_ID[user_id], name)
            self.assertEqual(MOP_IDS_BY_NAME[name], user_id)

    def test_roster_reads_all_pages_and_preserves_inactive_status(self) -> None:
        pages = [
            {
                "result": [
                    {"ID": "190", "ACTIVE": False},
                    {"ID": "225", "ACTIVE": True},
                    {"ID": "30", "ACTIVE": True},
                ],
                "next": 50,
            },
            {
                "result": [
                    {"ID": "226", "ACTIVE": "Y"},
                    {"ID": "227", "ACTIVE": "1"},
                    {"ID": "228", "ACTIVE": "N"},
                ],
            },
        ]
        with patch("sync_mop_report.execute_bitrix_method", side_effect=pages) as method:
            roster = fetch_bitrix_mop_roster(None, None)

        self.assertEqual([call.args[3]["start"] for call in method.call_args_list], [0, 50])
        self.assertEqual(
            {item["mopId"]: item["active"] for item in roster},
            {"190": False, "225": True, "226": True, "227": True, "228": False},
        )


if __name__ == "__main__":
    unittest.main()
