from __future__ import annotations

import unittest

from scripts.sync_mop_report import efficiency_header_row_index, trim_efficiency_matrix


class EfficiencySheetTest(unittest.TestCase):
    def test_trims_only_trailing_empty_rows_and_columns(self) -> None:
        rows = trim_efficiency_matrix([
            ["Заголовок", "", ""],
            ["МОП", "Показатель", "Коэффициент", ""],
            ["Ирина", 12, "80%"],
            ["", "", ""],
        ])

        self.assertEqual(rows, [
            ["Заголовок", "", ""],
            ["МОП", "Показатель", "Коэффициент"],
            ["Ирина", "12", "80%"],
        ])

    def test_uses_most_populated_leading_row_as_header(self) -> None:
        rows = [
            ["Коэффициент эффективности", "", ""],
            ["МОП", "Показатель", "Коэффициент"],
            ["Ирина", "12", "80%"],
        ]

        self.assertEqual(efficiency_header_row_index(rows), 1)


if __name__ == "__main__":
    unittest.main()
