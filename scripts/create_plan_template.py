from __future__ import annotations

from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "Шаблон плана МОП.xlsx"
SHEET_NAME = "Сводная за месяц"
AGGREGATE_PLAN_NAME = "Общий план"
MOP_NAMES = (
    "Черткова Ирина",
    "Попова Олеся",
    "Попова Юлия",
    "Губайдулина Заррина",
    "Тончу Ростислав",
    "Погребинский Артем",
    "Камболин Александр",
    "Жуков Лев",
    "Гавриленко Елена",
    "Войнов Данил",
    "Султанов Есен",
    "Парфенов Владислав",
)
HEADERS = ("МОП", "План по продажам", "Встречи", "Брони", "Ипотеки", "Эфир")


def inline_cell(reference: str, value: str, style: int = 0) -> str:
    style_attr = f' s="{style}"' if style else ""
    return f'<c r="{reference}" t="inlineStr"{style_attr}><is><t>{escape(value)}</t></is></c>'


def empty_cell(reference: str, style: int = 0) -> str:
    style_attr = f' s="{style}"' if style else ""
    return f'<c r="{reference}"{style_attr}/>'


def sheet_xml() -> str:
    rows = [
        f'<row r="1" ht="22" customHeight="1">{inline_cell("A1", "Месяц", 1)}{inline_cell("B1", "01.06.2026", 2)}</row>',
        '<row r="2" ht="9" customHeight="1"/>',
        '<row r="3" ht="30" customHeight="1">'
        + "".join(inline_cell(f"{column}3", header, 3) for column, header in zip("ABCDEF", HEADERS))
        + "</row>",
        '<row r="4" ht="24" customHeight="1">'
        + inline_cell("A4", AGGREGATE_PLAN_NAME, 6)
        + "".join(empty_cell(f"{column}4", 6) for column in "BCDEF")
        + "</row>",
    ]
    for row_number, mop_name in enumerate(MOP_NAMES, start=5):
        cells = [inline_cell(f"A{row_number}", mop_name, 4)]
        cells.extend(empty_cell(f"{column}{row_number}", 5) for column in "BCDEF")
        rows.append(f'<row r="{row_number}" ht="22" customHeight="1">{"".join(cells)}</row>')

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:F14"/>
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="3" topLeftCell="A4" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>
    <col min="1" max="1" width="28" customWidth="1"/>
    <col min="2" max="2" width="20" customWidth="1"/>
    <col min="3" max="5" width="14" customWidth="1"/>
    <col min="6" max="6" width="16" customWidth="1"/>
  </cols>
  <sheetData>{"".join(rows)}</sheetData>
  <autoFilter ref="A3:F14"/>
</worksheet>
"""


FILES = {
    "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
""",
    "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
""",
    "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
""",
    "xl/workbook.xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="{SHEET_NAME}" sheetId="1" r:id="rId1"/></sheets>
</workbook>
""",
    "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FF1F2937"/><name val="Calibri"/></font>
  </fonts>
  <fills count="5">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF2F8CFF"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEAF3FF"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEDE7FF"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD7DEE8"/></left>
      <right style="thin"><color rgb="FFD7DEE8"/></right>
      <top style="thin"><color rgb="FFD7DEE8"/></top>
      <bottom style="thin"><color rgb="FFD7DEE8"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="7">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="2" fillId="4" borderId="1" xfId="0"><alignment vertical="center"/></xf>
  </cellXfs>
</styleSheet>
""",
}


def write_file(archive: ZipFile, name: str, content: str) -> None:
    info = ZipInfo(name, date_time=(2026, 6, 3, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    archive.writestr(info, content.encode("utf-8"))


def main() -> None:
    with ZipFile(OUTPUT_PATH, "w") as archive:
        for name, content in FILES.items():
            write_file(archive, name, content)
        write_file(archive, "xl/worksheets/sheet1.xml", sheet_xml())
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
