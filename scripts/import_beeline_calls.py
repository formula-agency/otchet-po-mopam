from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import xlrd
except ImportError:  # pragma: no cover - handled in main for a readable CLI error
    xlrd = None  # type: ignore[assignment]

from import_megafon_calls import (
    ImportErrorWithHint,
    canonical_mop_names,
    empty_metric_row,
    filter_records_by_window,
    format_duration,
    parse_duration_seconds,
    parse_int,
    parse_payload_date,
    recompute_totals,
    sprint_start_for_date,
    update_filters,
    update_overview,
    write_payload,
    normalize_text,
)


BEELINE_SOURCE = "beeline_stat"
BEELINE_WARNING_PREFIX = "Билайн:"
BEELINE_MOP_ID = "__beeline_vats__"
BEELINE_MOP_NAME = "ВАТС Билайн (общий итог)"


@dataclass(frozen=True)
class BeelineCallRecord:
    day: date
    employee: str
    duration_seconds: int
    call_type: str
    status: str


@dataclass(frozen=True)
class BeelineSummaryRecord:
    total_calls: int
    air_time_seconds: int
    generated_on: date | None
    incoming_calls: int = 0
    missed_calls: int = 0
    outgoing_calls: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Beeline Stat.xls call export into dashboard data.")
    parser.add_argument("xls_file", help="Beeline Stat.xls export.")
    parser.add_argument(
        "--dashboard-data",
        default="dashboard/data/mop-report-data.json",
        help="Dashboard JSON file to update.",
    )
    return parser.parse_args()


def header_map(row: list[Any]) -> dict[str, int]:
    aliases = {
        "date": {"дата время"},
        "call_type": {"тип вызова"},
        "employee": {"абонент"},
        "extension": {"внутренний номер"},
        "duration": {"длительность"},
        "status": {"статус"},
    }
    found: dict[str, int] = {}
    for index, value in enumerate(row):
        normalized = normalize_text(value)
        for key, names in aliases.items():
            if normalized in names:
                found[key] = index
    return found


def parse_beeline_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()

    text = str(value or "").strip()
    if not text:
        return None

    for fmt in (
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d.%m.%y %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
        "%d/%m/%y",
        "%d/%m/%Y",
        "%d.%m.%y",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    return None


def parse_date_from_text(value: Any) -> date | None:
    text = str(value or "").strip()
    match = re.search(r"(\d{2}[./]\d{2}[./]\d{4})", text)
    return parse_beeline_date(match.group(1)) if match else None


def read_xls_rows(path: Path) -> list[list[Any]]:
    if xlrd is None:
        raise ImportErrorWithHint("Для чтения Stat.xls нужен пакет xlrd. Установите зависимости из requirements.txt.")

    try:
        book = xlrd.open_workbook(path)
    except Exception as exc:
        raise ImportErrorWithHint(f"Не удалось открыть xls файл: {exc}") from exc

    rows: list[list[Any]] = []
    for sheet in book.sheets():
        for row_index in range(sheet.nrows):
            values: list[Any] = []
            for column_index in range(sheet.ncols):
                values.append(sheet.cell_value(row_index, column_index))
            rows.append(values)
    return rows


def parse_beeline_records(path: Path) -> list[BeelineCallRecord]:
    rows = read_xls_rows(path)

    mapping: dict[str, int] | None = None
    start_index = 0
    for index, row in enumerate(rows[:40]):
        candidate = header_map(row)
        if {"date", "employee", "duration"} <= set(candidate):
            mapping = candidate
            start_index = index + 1
            break

    if not mapping:
        raise ImportErrorWithHint("Не нашел в Stat.xls колонки Дата, время, Абонент и Длительность.")

    records: list[BeelineCallRecord] = []
    for row in rows[start_index:]:
        max_index = max(mapping.values())
        if len(row) <= max_index:
            continue
        current_date = parse_beeline_date(row[mapping["date"]])
        employee = str(row[mapping["employee"]] or "").strip()
        if current_date is None or not employee:
            continue
        records.append(
            BeelineCallRecord(
                day=current_date,
                employee=employee,
                duration_seconds=parse_duration_seconds(row[mapping["duration"]]),
                call_type=str(row[mapping["call_type"]]).strip() if "call_type" in mapping else "",
                status=str(row[mapping["status"]]).strip() if "status" in mapping else "",
            )
        )

    if not records:
        raise ImportErrorWithHint("В Stat.xls не найдено строк звонков с датой и абонентом.")
    return sorted(records, key=lambda record: (record.day, record.employee))


def parse_beeline_summary(path: Path) -> BeelineSummaryRecord:
    rows = read_xls_rows(path)
    aliases = {
        "total": {"всего вызовов совершено"},
        "incoming": {"входящих"},
        "missed": {"не принятых"},
        "outgoing": {"исходящих"},
        "air": {"общее время разговоров"},
    }
    generated_on = next(
        (parsed for row in rows[:20] for value in row if (parsed := parse_date_from_text(value))),
        None,
    )

    for index, row in enumerate(rows):
        mapping: dict[str, int] = {}
        for column_index, value in enumerate(row):
            normalized = normalize_text(value)
            for key, names in aliases.items():
                if normalized in names:
                    mapping[key] = column_index
        if not {"total", "air"} <= set(mapping):
            continue

        for values in rows[index + 1 :]:
            if len(values) <= max(mapping.values()):
                continue
            total_calls = parse_int(values[mapping["total"]])
            air_time_seconds = parse_duration_seconds(values[mapping["air"]])
            if total_calls <= 0 and air_time_seconds <= 0:
                continue
            return BeelineSummaryRecord(
                total_calls=total_calls,
                air_time_seconds=air_time_seconds,
                generated_on=generated_on,
                incoming_calls=parse_int(values[mapping["incoming"]]) if "incoming" in mapping else 0,
                missed_calls=parse_int(values[mapping["missed"]]) if "missed" in mapping else 0,
                outgoing_calls=parse_int(values[mapping["outgoing"]]) if "outgoing" in mapping else 0,
            )

    raise ImportErrorWithHint("Не нашел в Beeline xls журнал звонков или таблицу общей статистики.")


def aggregate_beeline_records(
    records: list[BeelineCallRecord],
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
        by_week_mop[key]["beelineCallsFact"] += 1
        by_week_mop[key]["beelineAirTimeFactSeconds"] += record.duration_seconds
        if record.duration_seconds > 0:
            by_week_mop[key]["beelineAnsweredCalls"] += 1

    rows: list[dict[str, Any]] = []
    for (week_start, mop_name), metrics in sorted(by_week_mop.items(), key=lambda item: (item[0][0], item[0][1])):
        row = empty_metric_row(week_start, mop_name=mop_name, mop_id="", manual_aggregate=False)
        row.update(metrics)
        row["airTimeFact"] = format_duration(row["airTimeFactSeconds"])
        rows.append(row)
    return rows, dict(skipped_by_employee)


def aggregate_beeline_summary(summary: BeelineSummaryRecord, week_start: date) -> dict[str, Any]:
    row = empty_metric_row(
        week_start,
        mop_name=BEELINE_MOP_NAME,
        mop_id=BEELINE_MOP_ID,
        manual_aggregate=True,
        manual_source=BEELINE_SOURCE,
    )
    row.update(
        {
            "callsFact": summary.total_calls,
            "airTimeFactSeconds": summary.air_time_seconds,
            "airTimeFact": format_duration(summary.air_time_seconds),
            "beelineCallsFact": summary.total_calls,
            "beelineAirTimeFactSeconds": summary.air_time_seconds,
            "beelineIncomingCalls": summary.incoming_calls,
            "beelineMissedCalls": summary.missed_calls,
            "beelineOutgoingCalls": summary.outgoing_calls,
        }
    )
    return row


def clear_existing_beeline_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    beeline_keys = {
        "beelineCallsFact",
        "beelineAirTimeFactSeconds",
        "beelineAnsweredCalls",
        "beelineIncomingCalls",
        "beelineMissedCalls",
        "beelineOutgoingCalls",
        "beelineOnlyRow",
    }
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        if (
            row.get("beelineOnlyRow")
            or row.get("manualSource") == BEELINE_SOURCE
            or row.get("mopId") == BEELINE_MOP_ID
        ):
            continue

        beeline_calls = parse_int(row.get("beelineCallsFact"))
        beeline_air = parse_int(row.get("beelineAirTimeFactSeconds"))
        if beeline_calls or beeline_air:
            row["callsFact"] = max(0, parse_int(row.get("callsFact")) - beeline_calls)
            row["airTimeFactSeconds"] = max(0, parse_int(row.get("airTimeFactSeconds")) - beeline_air)
            row["airTimeFact"] = format_duration(row["airTimeFactSeconds"])

        for key in beeline_keys:
            row.pop(key, None)
        cleaned.append(row)
    return cleaned


def merge_beeline_rows(payload: dict[str, Any], beeline_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_rows = clear_existing_beeline_data(payload.get("baseRows", []))
    rows_by_key = {
        (str(row.get("weekStart", "")), str(row.get("mopName", ""))): row
        for row in base_rows
    }

    for import_row in beeline_rows:
        key = (str(import_row["weekStart"]), str(import_row["mopName"]))
        row = rows_by_key.get(key)
        if row is None:
            row = empty_metric_row(
                import_row_date(import_row),
                mop_name=str(import_row["mopName"]),
                mop_id=str(import_row.get("mopId", "")),
                manual_aggregate=bool(import_row.get("manualAggregate")),
                manual_source=BEELINE_SOURCE,
            )
            row["beelineOnlyRow"] = True
            base_rows.append(row)
            rows_by_key[key] = row

        row["callsFact"] = parse_int(row.get("callsFact")) + parse_int(import_row.get("callsFact"))
        row["airTimeFactSeconds"] = parse_int(row.get("airTimeFactSeconds")) + parse_int(import_row.get("airTimeFactSeconds"))
        row["airTimeFact"] = format_duration(row["airTimeFactSeconds"])
        row["beelineCallsFact"] = parse_int(import_row.get("beelineCallsFact"))
        row["beelineAirTimeFactSeconds"] = parse_int(import_row.get("beelineAirTimeFactSeconds"))
        row["beelineAnsweredCalls"] = parse_int(import_row.get("beelineAnsweredCalls"))
        row["beelineIncomingCalls"] = parse_int(import_row.get("beelineIncomingCalls"))
        row["beelineMissedCalls"] = parse_int(import_row.get("beelineMissedCalls"))
        row["beelineOutgoingCalls"] = parse_int(import_row.get("beelineOutgoingCalls"))
        row.pop("sharedPlanOnlyRow", None)

    payload["baseRows"] = sorted(
        base_rows,
        key=lambda row: (str(row.get("weekStart", "")), str(row.get("mopName", ""))),
    )
    return payload["baseRows"]


def import_row_date(row: dict[str, Any]) -> date:
    value = str(row.get("weekStart", ""))
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def replace_beeline_warnings(
    payload: dict[str, Any],
    file_name: str,
    skipped_by_employee: dict[str, int],
    *,
    has_mop_breakdown: bool = True,
) -> None:
    warnings = [
        warning
        for warning in payload.get("warnings", [])
        if not str(warning).startswith(BEELINE_WARNING_PREFIX)
    ]
    if has_mop_breakdown:
        warnings.append(f"{BEELINE_WARNING_PREFIX} звонки и эфир импортированы из файла {file_name} по абонентам.")
        skipped_total = sum(skipped_by_employee.values())
        if skipped_total:
            warnings.append(f"{BEELINE_WARNING_PREFIX} пропущено {skipped_total} звонков абонентов вне списка МОП.")
    else:
        warnings.append(
            f"{BEELINE_WARNING_PREFIX} звонки и эфир импортированы из файла {file_name} как общий итог без разбивки по МОП.",
        )
    payload["warnings"] = warnings


def main() -> int:
    try:
        args = parse_args()
        xls_path = Path(args.xls_file)
        data_path = Path(args.dashboard_data)
        if not xls_path.exists():
            raise ImportErrorWithHint(f"Файл не найден: {xls_path}")
        if not data_path.exists():
            raise ImportErrorWithHint(f"Файл данных dashboard не найден: {data_path}")

        payload = json.loads(data_path.read_text(encoding="utf-8"))
        report_from = parse_payload_date(payload, "from")
        report_to = parse_payload_date(payload, "to")

        try:
            records = parse_beeline_records(xls_path)
        except ImportErrorWithHint:
            records = []

        if records:
            max_export_date = max(record.day for record in records)
            upper_bound = max(report_to, max_export_date) if report_to else max_export_date
            records = filter_records_by_window(records, report_from, upper_bound)
            new_rows, skipped_by_employee = aggregate_beeline_records(records, canonical_mop_names(payload))
            mode = "stat_xls"
            record_count = len(records)
            has_mop_breakdown = True
        else:
            summary = parse_beeline_summary(xls_path)
            summary_date = summary.generated_on or report_to or date.today()
            upper_bound = max(report_to, summary_date) if report_to else summary_date
            new_rows = [aggregate_beeline_summary(summary, sprint_start_for_date(summary_date))]
            skipped_by_employee = {}
            mode = "summary_xls"
            record_count = summary.total_calls
            has_mop_breakdown = False

        payload.setdefault("report", {})["to"] = upper_bound.isoformat()
        merge_beeline_rows(payload, new_rows)

        import_meta = {
            "fileName": xls_path.name,
            "importedAt": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "rowCount": len(new_rows),
            "recordCount": record_count,
            "importedCallCount": sum(row.get("callsFact", 0) for row in new_rows),
            "importedAirTimeSeconds": sum(row.get("airTimeFactSeconds", 0) for row in new_rows),
            "skippedCallCount": sum(skipped_by_employee.values()),
            "skippedEmployees": skipped_by_employee,
            "hasMopBreakdown": has_mop_breakdown,
            "hasAirTime": True,
        }

        payload["manualImports"] = {
            **payload.get("manualImports", {}),
            BEELINE_SOURCE: import_meta,
        }
        payload["generatedAt"] = datetime.now().isoformat(timespec="seconds")

        replace_beeline_warnings(
            payload,
            xls_path.name,
            skipped_by_employee,
            has_mop_breakdown=has_mop_breakdown,
        )
        update_filters(payload, new_rows)
        recompute_totals(payload)
        update_overview(payload)
        write_payload(payload, data_path)

        print(f"Imported Beeline calls: {import_meta['importedCallCount']}")
        print(f"Imported Beeline air time: {format_duration(import_meta['importedAirTimeSeconds'])}")
        print(f"Sprint rows: {len(new_rows)}")
        print(f"Dashboard data: {data_path}")
        return 0
    except ImportErrorWithHint as exc:
        print(f"Import error: {exc}")
        return 2
    except Exception as exc:
        print(f"Unhandled error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
