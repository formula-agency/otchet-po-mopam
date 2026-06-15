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
DEFAULT_MOP_NAMES = (
    "Черткова Ирина",
    "Газисова Мария",
    "Попова Олеся",
    "Попова Юлия",
    "Губайдулина Заррина",
    "Тончу Ростислав",
    "Погребинский Артем",
    "Камболин Александр",
    "Жуков Лев",
    "Гавриленко Елена",
)
METRIC_ZEROES = {
    "salesPlan": 0,
    "salesFact": 0,
    "meetingsPlan": 0,
    "meetingsFact": 0,
    "reservationsPlan": 0,
    "reservationsFact": 0,
    "approvedMortgagesPlan": 0,
    "approvedMortgagesFact": 0,
    "callsFact": 0,
    "airTimePlanSeconds": 0,
    "airTimeFactSeconds": 0,
    "targetMinutesAfterMeetingFactSeconds": 0,
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


@dataclass(frozen=True)
class CallHistoryRecord:
    day: date
    employee: str
    duration_seconds: int
    call_type: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import MegaFon VATS call exports into dashboard data.")
    parser.add_argument("xlsx_file", help="MegaFon VATS xlsx export with call counts or external call history.")
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


def parse_duration_seconds(value: Any) -> int:
    text = str(value or "").strip()
    if not text or text == "-":
        return 0
    match = re.match(r"^(\d+):(\d{2}):(\d{2})$", text)
    if match:
        hours, minutes, seconds = (int(part) for part in match.groups())
        return hours * 3600 + minutes * 60 + seconds
    try:
        serial = float(text.replace(",", "."))
    except ValueError:
        return 0
    if 0 <= serial < 1:
        return round(serial * 86400)
    return int(serial)


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
    minutes, secs = divmod(max(0, seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


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


def history_header_map(row: list[str]) -> dict[str, int]:
    aliases = {
        "call_type": {"тип звонка"},
        "employee": {"сотрудник"},
        "date": {"дата"},
        "duration": {"длительность"},
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


def parse_megafon_history_records(path: Path) -> list[CallHistoryRecord]:
    sheets = read_xlsx_rows(path)
    for _sheet_name, rows in sheets.items():
        mapping: dict[str, int] | None = None
        start_index = 0
        for index, row in enumerate(rows[:30]):
            candidate = history_header_map(row)
            if {"employee", "date", "duration"} <= set(candidate):
                mapping = candidate
                start_index = index + 1
                break
        if not mapping:
            continue

        records: list[CallHistoryRecord] = []
        for row in rows[start_index:]:
            max_index = max(mapping.values())
            if len(row) <= max_index:
                continue
            current_date = parse_iso_date(row[mapping["date"]])
            if current_date is None:
                continue
            employee = str(row[mapping["employee"]] or "").strip()
            if not employee:
                continue
            records.append(
                CallHistoryRecord(
                    day=current_date,
                    employee=employee,
                    duration_seconds=parse_duration_seconds(row[mapping["duration"]]),
                    call_type=str(row[mapping["call_type"]]).strip() if "call_type" in mapping else "",
                )
            )
        if records:
            return sorted(records, key=lambda record: (record.day, record.employee))

    raise ImportErrorWithHint("Не нашел в xlsx историю с колонками Сотрудник, Дата и Длительность.")


def empty_metric_row(
    week_start: date,
    mop_name: str = MEGAFON_MOP_NAME,
    mop_id: str = MEGAFON_MOP_ID,
    manual_aggregate: bool = True,
    manual_source: str = MEGAFON_SOURCE,
) -> dict[str, Any]:
    row = {
        "weekStart": week_start.isoformat(),
        "weekEnd": sprint_end_for_start(week_start).isoformat(),
        "weekLabel": format_week_label(week_start),
        "mopId": mop_id,
        "mopName": mop_name,
        "airTimePlan": "00:00",
        "airTimeFact": "00:00",
        **METRIC_ZEROES,
    }
    if manual_aggregate:
        row["manualSource"] = manual_source
        row["manualAggregate"] = True
    return row


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


def canonical_mop_names(payload: dict[str, Any]) -> dict[str, str]:
    names = set(DEFAULT_MOP_NAMES)
    names.update(str(name) for name in (payload.get("filters") or {}).get("mopNames", []) if name)
    names.update(
        str(row.get("mopName"))
        for row in payload.get("baseRows", [])
        if row.get("mopName") and not row.get("manualAggregate")
    )
    names.discard(MEGAFON_MOP_NAME)
    return {normalize_text(name): name for name in names if normalize_text(name)}


def filter_records_by_window(records: list[Any], report_from: date | None, report_to: date | None) -> list[Any]:
    filtered = records
    if report_from:
        filtered = [record for record in filtered if record.day >= report_from]
    if report_to:
        filtered = [record for record in filtered if record.day <= report_to]
    return filtered


def aggregate_history_records(
    records: list[CallHistoryRecord],
    name_map: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_week_mop: dict[tuple[date, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    skipped_by_employee: dict[str, int] = defaultdict(int)

    for record in records:
        mop_name = name_map.get(normalize_text(record.employee))
        if not mop_name:
            skipped_by_employee[record.employee] += 1
            continue
        key = (sprint_start_for_date(record.day), mop_name)
        by_week_mop[key]["callsFact"] += 1
        by_week_mop[key]["airTimeFactSeconds"] += record.duration_seconds
        by_week_mop[key]["megafonCallsFact"] += 1
        by_week_mop[key]["megafonAirTimeFactSeconds"] += record.duration_seconds
        if record.duration_seconds > 0:
            by_week_mop[key]["megafonAnsweredCalls"] += 1

    rows: list[dict[str, Any]] = []
    for (week_start, mop_name), metrics in sorted(by_week_mop.items(), key=lambda item: (item[0][0], item[0][1])):
        row = empty_metric_row(week_start, mop_name=mop_name, mop_id="", manual_aggregate=False)
        row.update(metrics)
        row["airTimeFact"] = format_duration(row["airTimeFactSeconds"])
        row["callsSource"] = MEGAFON_SOURCE
        row["airTimeSource"] = MEGAFON_SOURCE
        rows.append(row)
    return rows, dict(skipped_by_employee)


def clear_existing_megafon_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    megafon_keys = {
        "callsSource",
        "airTimeSource",
        "callsFactBaseBeforeMegafon",
        "airTimeFactSecondsBaseBeforeMegafon",
        "megafonCallsFact",
        "megafonAirTimeFactSeconds",
        "megafonAnsweredCalls",
    }
    for row in rows:
        if row.get("manualSource") == MEGAFON_SOURCE or row.get("mopId") == MEGAFON_MOP_ID:
            continue
        if row.get("callsSource") == MEGAFON_SOURCE:
            row["callsFact"] = parse_int(row.get("callsFactBaseBeforeMegafon"))
        if row.get("airTimeSource") == MEGAFON_SOURCE:
            row["airTimeFactSeconds"] = parse_int(row.get("airTimeFactSecondsBaseBeforeMegafon"))
            row["airTimeFact"] = format_duration(row["airTimeFactSeconds"])
        for key in megafon_keys:
            row.pop(key, None)
        cleaned.append(row)
    return cleaned


def merge_history_rows(payload: dict[str, Any], megafon_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_rows = clear_existing_megafon_data(payload.get("baseRows", []))
    rows_by_key = {
        (str(row.get("weekStart", "")), str(row.get("mopName", ""))): row
        for row in base_rows
    }

    for import_row in megafon_rows:
        key = (str(import_row["weekStart"]), str(import_row["mopName"]))
        row = rows_by_key.get(key)
        if row is None:
            row = empty_metric_row(
                parse_iso_date(import_row["weekStart"]) or date.today(),
                mop_name=str(import_row["mopName"]),
                mop_id=str(import_row.get("mopId", "")),
                manual_aggregate=False,
            )
            base_rows.append(row)
            rows_by_key[key] = row

        base_calls = parse_int(row.get("callsFact"))
        base_air = parse_int(row.get("airTimeFactSeconds"))
        row["callsFactBaseBeforeMegafon"] = base_calls
        row["airTimeFactSecondsBaseBeforeMegafon"] = base_air
        row["callsFact"] = base_calls + parse_int(import_row.get("callsFact"))
        row["airTimeFactSeconds"] = base_air + parse_int(import_row.get("airTimeFactSeconds"))
        row["airTimeFact"] = format_duration(row["airTimeFactSeconds"])
        row["callsSource"] = MEGAFON_SOURCE
        row["airTimeSource"] = MEGAFON_SOURCE
        row["megafonCallsFact"] = parse_int(import_row.get("megafonCallsFact"))
        row["megafonAirTimeFactSeconds"] = parse_int(import_row.get("megafonAirTimeFactSeconds"))
        row["megafonAnsweredCalls"] = parse_int(import_row.get("megafonAnsweredCalls"))
        row.pop("sharedPlanOnlyRow", None)

    payload["baseRows"] = sorted(
        base_rows,
        key=lambda row: (str(row.get("weekStart", "")), str(row.get("mopName", ""))),
    )
    return payload["baseRows"]


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
    totals["targetMinutesAfterMeetingFact"] = format_duration(
        totals["targetMinutesAfterMeetingFactSeconds"]
    )
    payload["totals"] = totals


def update_overview(payload: dict[str, Any]) -> None:
    rows = payload.get("baseRows", [])
    mop_names = {row.get("mopName") for row in rows if row.get("mopName") and not row.get("manualAggregate")}
    weeks = {row.get("weekStart") for row in rows if row.get("weekStart")}
    payload["overview"] = {"mopCount": len(mop_names), "weekCount": len(weeks)}


def replace_megafon_warnings(
    payload: dict[str, Any],
    file_name: str,
    metric: str,
    *,
    has_mop_breakdown: bool,
    has_air_time: bool,
    skipped_by_employee: dict[str, int] | None = None,
) -> None:
    warnings = [
        warning
        for warning in payload.get("warnings", [])
        if not str(warning).startswith("МегаФон ВАТС:")
        and not str(warning).startswith("Звонки не посчитаны:")
    ]
    if has_mop_breakdown:
        skipped_total = sum((skipped_by_employee or {}).values())
        warnings.append(f"МегаФон ВАТС: звонки и эфир импортированы из файла {file_name} по сотрудникам.")
        if skipped_total:
            warnings.append(f"МегаФон ВАТС: пропущено {skipped_total} звонков сотрудников вне списка МОП.")
    else:
        metric_label = "Всего" if metric == "total" else "Исходящие"
        warnings.extend(
            [
                f"МегаФон ВАТС: звонки импортированы из файла {file_name} как общий итог без разбивки по МОП.",
                f"МегаФон ВАТС: в показатель звонков взята колонка '{metric_label}'.",
            ]
        )
    if not has_air_time:
        warnings.append("МегаФон ВАТС: в этом файле нет эфирного времени, поэтому эфир факт не изменен.")
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
        report_from = parse_payload_date(payload, "from")
        report_to = parse_payload_date(payload, "to")

        try:
            history_records = parse_megafon_history_records(xlsx_path)
        except ImportErrorWithHint:
            history_records = []

        if history_records:
            max_export_date = max(record.day for record in history_records)
            upper_bound = max(report_to, max_export_date) if report_to else max_export_date
            history_records = filter_records_by_window(history_records, report_from, upper_bound)
            payload.setdefault("report", {})["to"] = upper_bound.isoformat()

            new_rows, skipped_by_employee = aggregate_history_records(history_records, canonical_mop_names(payload))
            merge_history_rows(payload, new_rows)
            import_meta = {
                "fileName": xlsx_path.name,
                "importedAt": datetime.now().isoformat(timespec="seconds"),
                "mode": "history",
                "rowCount": len(new_rows),
                "recordCount": len(history_records),
                "importedCallCount": sum(row.get("callsFact", 0) for row in new_rows),
                "importedAirTimeSeconds": sum(row.get("airTimeFactSeconds", 0) for row in new_rows),
                "skippedCallCount": sum(skipped_by_employee.values()),
                "skippedEmployees": skipped_by_employee,
                "hasMopBreakdown": True,
                "hasAirTime": True,
            }
            replace_megafon_warnings(
                payload,
                xlsx_path.name,
                args.metric,
                has_mop_breakdown=True,
                has_air_time=True,
                skipped_by_employee=skipped_by_employee,
            )
            printed_calls = import_meta["importedCallCount"]
            printed_rows = len(new_rows)
            printed_air = import_meta["importedAirTimeSeconds"]
        else:
            records = parse_megafon_daily_records(xlsx_path)
            max_export_date = max(record.day for record in records)
            upper_bound = max(report_to, max_export_date) if report_to else max_export_date
            records = filter_records_by_window(records, report_from, upper_bound)
            payload.setdefault("report", {})["to"] = upper_bound.isoformat()

            new_rows = aggregate_records(records, args.metric)
            base_rows = clear_existing_megafon_data(payload.get("baseRows", []))
            payload["baseRows"] = sorted(
                [*base_rows, *new_rows],
                key=lambda row: (str(row.get("weekStart", "")), str(row.get("mopName", ""))),
            )
            import_meta = {
                "fileName": xlsx_path.name,
                "importedAt": datetime.now().isoformat(timespec="seconds"),
                "mode": "daily_counts",
                "metric": args.metric,
                "rowCount": len(new_rows),
                "recordCount": len(records),
                "hasMopBreakdown": False,
                "hasAirTime": False,
            }
            replace_megafon_warnings(
                payload,
                xlsx_path.name,
                args.metric,
                has_mop_breakdown=False,
                has_air_time=False,
            )
            printed_calls = sum(row["callsFact"] for row in new_rows)
            printed_rows = len(new_rows)
            printed_air = 0

        payload["manualImports"] = {
            **payload.get("manualImports", {}),
            MEGAFON_SOURCE: import_meta,
        }
        payload["generatedAt"] = datetime.now().isoformat(timespec="seconds")

        update_filters(payload, new_rows)
        recompute_totals(payload)
        update_overview(payload)
        write_payload(payload, data_path)

        print(f"Imported MegaFon VATS calls: {printed_calls}")
        print(f"Imported MegaFon VATS air time: {format_duration(printed_air)}")
        print(f"Sprint rows: {printed_rows}")
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
