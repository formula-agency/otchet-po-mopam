import sys
import unittest
from datetime import date
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from sync_mop_report import MANUAL_SALES_DATE_OVERRIDES  # noqa: E402


class SalesDateOverrideTest(unittest.TestCase):
    def test_zhukov_sale_5824_stays_in_august(self) -> None:
        self.assertEqual(MANUAL_SALES_DATE_OVERRIDES["5824"], date(2026, 8, 17))

    def test_corrected_sales_stay_in_august(self) -> None:
        self.assertEqual(MANUAL_SALES_DATE_OVERRIDES["5377"], date(2026, 8, 31))
        self.assertEqual(MANUAL_SALES_DATE_OVERRIDES["5891"], date(2026, 8, 31))
        self.assertEqual(MANUAL_SALES_DATE_OVERRIDES["5974"], date(2026, 8, 31))


if __name__ == "__main__":
    unittest.main()
