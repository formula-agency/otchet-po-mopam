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

    def test_sale_5730_uses_bitrix_win_date_in_september(self) -> None:
        self.assertEqual(MANUAL_SALES_DATE_OVERRIDES["5730"], date(2026, 9, 1))

    def test_october_sales_are_accounted_for_in_september(self) -> None:
        self.assertEqual(MANUAL_SALES_DATE_OVERRIDES["6276"], date(2026, 9, 30))
        self.assertEqual(MANUAL_SALES_DATE_OVERRIDES["6580"], date(2026, 9, 30))


if __name__ == "__main__":
    unittest.main()
