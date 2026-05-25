from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZipFile


XML_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
MEGAFON_MOP_ID = "__megafon_vats__"
MEGAFON_MOP_NAME = "ВАТС МегаФон (общий итог)"
MEGAFON_SOURCE = "megafon_vats"
METRIC_ZEROES = {
    "meetingsPlan": 0,
    "meetingsFact": 0,
    "reservationsPlan": 0,
    "reservationsFact": 0,
    "approvedMortgagesPlan": 0,
    "approvedMortgagesFact": 0,
    "callsPlan": 0,
    "callsFact": 0,
    "airTimePlanSeconds": 0,
    "airTimeFactSeconds": 0,
}


class ImportErrorWithHint(RuntimeError):
    pass


@dataclass(frozen=True)
class DailyCallRecord:
    day: date
    total: int
    incoming: int
    missed: int
    outgoing: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import aggregate MegaFon VATS call counts into dashboard data.")
    parser.add_argument("xlsx_file", help="MegaFon VATS xlsx export, for example 'Отчет по количеству звонков ...xlsx'.")
    parser.add_argument(
        "--dashboard-data",
        default="dashboard/data/mop-report-data.json",
        help="Dashboard JSON file to update.",
    )
    parser.add_argument(
        "--metric",
        choices=("total", "outgoing"),
        default="total",
        help="Which MegaFon column to use as calls fact.",
    )
    return parser.parse_args()


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я_ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_int(value: Any) -> int:
    text = str(value or "").strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not text or text == "-":
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    try:
        serial = float(text)
    except ValueError:
        return None
    if 1 <= serial <= 80000:
        return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
    return None


def sprint_start_for_date(current_date: date) -> date:
    sprint_day = min(22, 1 + ((current_date.day - 1) // 7) * 7)
    return date(current_date.year, current_date.month, sprint_day)


def month_end_for_date(current_date: date) -> date:
    if current_date.month == 12:
        next_month = date(current_date.year + 1, 1, 1)
    else:
        next_month = date(current_date.year, current_date.month + 1, 1)
    return next_month - timedelta(days=1)


def sprint_end_for_start(week_start: date) -> date:
    if week_start.day >= 22:
        return month_end_for_date(week_start)
    return week_start + timedelta(days=6)


def format_short_date(value: date) -> str:
    return value.strftime("%d.%m")


def format_sheet_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def format_week_label(week_start: date) -> str:
    return f"{format_short_date(week_start)}-{format_sheet_date(sprint_end_for_start(week_start))}"


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def column_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        return 0
    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def inline_text(cell: ET.Element) -> str:
    inline = cell.find("a:is", XML_NS)
    if inline is None:
        return ""
    return "".join(text.text or "" for text in inline.findall(".//a:t", XML_NS))


def read_xlsx_rows(path: Path) -> dict[str, list[list[str]]]:
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relationships}

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("a:si", XML_NS):
                shared_strings.append("".join(text.text or "" for text in item.findall(".//a:t", XML_NS)))

        result: dict[str, list[list[str]]] = {}
        for sheet in workbook.findall("a:sheets/a:sheet", XML_NS):
            title = sheet.attrib.get("name", "")
            rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            if not rel_id:
                continue
            target = relmap[rel_id]
            sheet_path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
            root = ET.fromstring(archive.read(sheet_path))
            rows: list[list[str]] = []
            for row in root.findall("a:sheetData/a:row", XML_NS):
                values: list[str] = []
                for cell in row.findall("a:c", XML_NS):
                    index = column_index(cell.attrib.get("r", "A"))
                    while len(values) <= index:
                        values.append("")
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("a:v", XML_NS)
                    if cell_type == "s" and value_node is not None:
                        value = shared_strings[int(value_node.text or 0)]
                    elif cell_type == "inlineStr":
                        value = inline_text(cell)
                    elif value_node is not None:
                        value = value_node.text or ""
                    else:
                        value = ""
                    values[index] = value
                rows.append(values)
            result[title] = rows
        return result


def header_map(row: list[str]) -> dict[str, int]:
    aliases = {
        "date": {"дата"},
        "total": {"всего"},
        "incoming": {"входящие"},
        "missed": {"пропущенные"},
        "outgoing": {"исходящие"},
    }
    found: dict[str, int] = {}
    for index, value in enumerate(row):
        normalized = normalize_text(value)
        for key, names in aliases.items():
            if normalized in names:
                found[key] = index
    return found


def parse_megafon_daily_records(path: Path) -> list[DailyCallRecord]:
    sheets = read_xlsx_rows(path)
    preferred_sheets = sorted(
        sheets.items(),
        key=lambda item: 0 if "по дням" in normalize_text(item[0]) else 1,
    )

    for _sheet_name, rows in preferred_sheets:
        mapping: dict[str, int] | None = None
        start_index = 0
        for index, row in enumerate(rows[:20]):
            candidate = header_map(row)
            if {"date", "total", "incoming", "missed", "outgoing"} <= set(candidate):
                mapping = candidate
                start_index = index + 1
                break
        if not mapping:
            continue

        records: list[DailyCallRecord] = []
        for row in rows[start_index:]:
            max_index = max(mapping.values())
            if len(row) <= max_index:
                continue
            current_date = parse_iso_date(row[mapping["date"]])
            if current_date is None:
                continue
            records.append(
                DailyCallRecord(
                    day=current_date,
                    total=parse_int(row[mapping["total"]]),
                    incoming=parse_int(row[mapping["incoming"]]),
                    missed=parse_int(row[mapping["missed"]]),
                    outgoing=parse_int(row[mapping["outgoing"]]),
                )
            )
        if records:
            return sorted(records, key=lambda record: record.day)

    raise ImportErrorWithHint("Не нашел в xlsx лист с колонками Дата, Всего, Входящие, Пропущенные, Исходящие.")


def empty_metric_row(week_start: date) -> dict[str, Any]:
    return {
        "weekStart": week_start.isoformat(),
        "weekEnd": sprint_end_for_start(week_start).isoformat(),
        "weekLabel": format_week_label(week_start),
        "mopId": MEGAFON_MOP_ID,
        "mopName": MEGAFON_MOP_NAME,
        "manualSource": MEGAFON_SOURCE,
        "manualAggregate": True,
        "airTimePlan": "00:00:00",
        "airTimeFact": "00:00:00",
        **METRIC_ZEROES,
    }


def aggregate_records(records: list[DailyCallRecord], metric: str) -> list[dict[str, Any]]:
    by_week: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in records:
        week_start = sprint_start_for_date(record.day)
        by_week[week_start]["callsFact"] += record.total if metric == "total" else record.outgoing
        by_week[week_start]["megafonTotalCalls"] += record.total
        by_week[week_start]["megafonIncomingCalls"] += record.incoming
        by_week[week_start]["megafonMissedCalls"] += record.missed
        by_week[week_start]["megafonOutgoingCalls"] += record.outgoing

    rows: list[dict[str, Any]] = []
    for week_start in sorted(by_week):
        row = empty_metric_row(week_start)
        row.update(by_week[week_start])
        rows.append(row)
    return rows


def parse_payload_date(payload: dict[str, Any], key: str) -> date | None:
    value = (payload.get("report") or {}).get(key)
    return parse_iso_date(value)


def update_filters(payload: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    filters = payload.setdefault("filters", {})
    weeks = {str(week) for week in filters.get("weeks", []) if week}
    weeks.update(str(row["weekStart"]) for row in rows)
    filters["weeks"] = sorted(weeks)
    if weeks:
        filters["minWeek"] = min(weeks)
        filters["maxWeek"] = max(weeks)


def recompute_totals(payload: dict[str, Any]) -> None:
    totals = {key: 0 for key in METRIC_ZEROES}
    for row in payload.get("baseRows", []):
        for key in totals:
            totals[key] += parse_int(row.get(key))
    totals["airTimePlan"] = format_duration(totals["airTimePlanSeconds"])
    totals["airTimeFact"] = format_duration(totals["airTimeFactSeconds"])
    payload["totals"] = totals


def update_overview(payload: dict[str, Any]) -> None:
    rows = payload.get("baseRows", [])
    mop_names = {row.get("mopName") for row in rows if row.get("mopName") and not row.get("manualAggregate")}
    weeks = {row.get("weekStart") for row in rows if row.get("weekStart")}
    payload["overview"] = {"mopCount": len(mop_names), "weekCount": len(weeks)}


def replace_megafon_warnings(payload: dict[str, Any], file_name: str, metric: str) -> None:
    warnings = [
        warning
        for warning in payload.get("warnings", [])
        if not str(warning).startswith("МегаФон ВАТС:")
        and not str(warning).startswith("Звонки не посчитаны:")
    ]
    metric_label = "Всего" if metric == "total" else "Исходящие"
    warnings.extend(
        [
            f"МегаФон ВАТС: звонки импортированы из файла {file_name} как общий итог без разбивки по МОП.",
            f"МегаФон ВАТС: в показатель звонков взята колонка '{metric_label}'.",
            "МегаФон ВАТС: в этом файле нет эфирного времени, поэтому эфир факт не изменен.",
        ]
    )
    payload["warnings"] = warnings


def write_payload(payload: dict[str, Any], data_path: Path) -> None:
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    data_path.write_text(f"{json_text}\n", encoding="utf-8")
    js_path = data_path.with_suffix(".js")
    js_path.write_text(f"window.MOP_REPORT_DASHBOARD_DATA = {json_text};\n", encoding="utf-8")


def main() -> int:
    try:
        args = parse_args()
        xlsx_path = Path(args.xlsx_file)
        data_path = Path(args.dashboard_data)
        if not xlsx_path.exists():
            raise ImportErrorWithHint(f"Файл не найден: {xlsx_path}")
        if not data_path.exists():
            raise ImportErrorWithHint(f"Файл данных dashboard не найден: {data_path}")

        payload = json.loads(data_path.read_text(encoding="utf-8"))
        records = parse_megafon_daily_records(xlsx_path)

        report_from = parse_payload_date(payload, "from")
        report_to = parse_payload_date(payload, "to")
        max_export_date = max(record.day for record in records)
        if report_from:
            records = [record for record in records if record.day >= report_from]
        if report_to:
            upper_bound = max(report_to, max_export_date)
            records = [record for record in records if record.day <= upper_bound]
            payload.setdefault("report", {})["to"] = upper_bound.isoformat()

        new_rows = aggregate_records(records, args.metric)
        base_rows = [
            row
            for row in payload.get("baseRows", [])
            if row.get("manualSource") != MEGAFON_SOURCE and row.get("mopId") != MEGAFON_MOP_ID
        ]
        payload["baseRows"] = sorted(
            [*base_rows, *new_rows],
            key=lambda row: (str(row.get("weekStart", "")), str(row.get("mopName", ""))),
        )
        payload["manualImports"] = {
            **payload.get("manualImports", {}),
            MEGAFON_SOURCE: {
                "fileName": xlsx_path.name,
                "importedAt": datetime.now().isoformat(timespec="seconds"),
                "metric": args.metric,
                "rowCount": len(new_rows),
                "recordCount": len(records),
                "hasMopBreakdown": False,
                "hasAirTime": False,
            },
        }
        payload["generatedAt"] = datetime.now().isoformat(timespec="seconds")

        update_filters(payload, new_rows)
        recompute_totals(payload)
        update_overview(payload)
        replace_megafon_warnings(payload, xlsx_path.name, args.metric)
        write_payload(payload, data_path)

        print(f"Imported MegaFon VATS calls: {sum(row['callsFact'] for row in new_rows)}")
        print(f"Sprint rows: {len(new_rows)}")
        print(f"Dashboard data: {data_path}")
        return 0
    except ImportErrorWithHint as exc:
        print(f"Import error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Unhandled error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
