from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from import_beeline_calls import (
    BEELINE_SOURCE,
    BeelineCallRecord,
    BeelineSummaryRecord,
    aggregate_beeline_records,
    aggregate_beeline_summary,
    clear_existing_beeline_data,
    merge_beeline_rows,
    parse_beeline_records,
    parse_beeline_summary,
)
from import_megafon_calls import (
    MEGAFON_SOURCE,
    CallHistoryRecord,
    ImportErrorWithHint,
    aggregate_history_records,
    canonical_mop_names,
    clear_existing_megafon_data,
    empty_metric_row,
    filter_records_by_window,
    format_duration,
    merge_history_rows,
    normalize_text,
    parse_duration_seconds,
    parse_int,
    parse_megafon_history_records,
    parse_payload_date,
    recompute_totals,
    sprint_start_for_date,
    update_filters,
    update_overview,
    write_payload,
)


DEFAULT_VATS_DIR = Path("vats data")
DEFAULT_DATA_PATH = Path("dashboard/data/mop-report-data.json")
LEGACY_MEGAFON_HISTORY = Path("manual-data/megafon-vats-history.xlsx")
LEGACY_BEELINE_STAT = Path("manual-data/beeline-stat.xls")
CRM_CALLS_SOURCE = "crm_calls_export"
CRM_CALLS_WARNING_PREFIX = "CRM звонки:"
RANGE_PATTERN = re.compile(
    r"^\s*(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*-\s*"
    r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*$",
)
SUM_FIELDS = {
    "callsFact",
    "completedCallsFact",
    "targetCallsFact",
    "targetSuccessfulCallsFact",
    "airTimeFactSeconds",
    "targetMinutesAfterMeetingPlanSeconds",
    "targetMinutesAfterMeetingFactSeconds",
    "beelineCallsFact",
    "beelineAirTimeFactSeconds",
    "beelineAnsweredCalls",
    "beelineIncomingCalls",
    "beelineMissedCalls",
    "beelineOutgoingCalls",
    "crmCallsFact",
    "crmTargetCallsFact",
    "crmTargetSuccessfulCallsFact",
    "crmAirTimeFactSeconds",
}
COMPLETED_CALL_CLASSIFICATIONS = {
    "сервисный звонок",
    "нецелевой звонок",
    "целевой нерезультативный",
    "целевой результативный",
}


@dataclass(frozen=True)
class SourceRange:
    path: Path
    start: date
    end: date


@dataclass(frozen=True)
class BeelineSummarySource:
    summary: BeelineSummaryRecord
    source_range: SourceRange


@dataclass(frozen=True)
class CsvCallRecord:
    path: Path
    day: date
    employee: str
    duration_seconds: int
    classification: str
    source_kind: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import all MegaFon and Beeline call exports from dated folders into dashboard data.",
    )
    parser.add_argument(
        "--vats-dir",
        default=str(DEFAULT_VATS_DIR),
        help="Directory with dated subfolders such as 01.06-03.06.",
    )
    parser.add_argument(
        "--dashboard-data",
        default=str(DEFAULT_DATA_PATH),
        help="Dashboard JSON file to update.",
    )
    parser.add_argument(
        "--no-legacy",
        action="store_true",
        help="Do not include the existing manual-data MegaFon and Beeline files.",
    )
    return parser.parse_args()


def parse_folder_range(name: str, anchor: date) -> tuple[date, date] | None:
    match = RANGE_PATTERN.match(name)
    if not match:
        return None
    start_day, start_month, start_year, end_day, end_month, end_year = match.groups()
    resolved_end_year = int(end_year) if end_year else anchor.year
    resolved_start_year = int(start_year) if start_year else resolved_end_year
    if not start_year and (int(start_month), int(start_day)) > (int(end_month), int(end_day)):
        resolved_start_year -= 1
    try:
        start = date(resolved_start_year, int(start_month), int(start_day))
        end = date(resolved_end_year, int(end_month), int(end_day))
    except ValueError as exc:
        raise ImportErrorWithHint(f"Некорректный диапазон дат в имени папки '{name}': {exc}") from exc
    if start > end:
        raise ImportErrorWithHint(f"Начало диапазона позже конца в имени папки '{name}'.")
    return start, end


def find_declared_range(path: Path, vats_dir: Path, anchor: date) -> tuple[date, date] | None:
    try:
        relative_parent = path.parent.resolve().relative_to(vats_dir.resolve())
    except ValueError:
        return None
    for part in reversed(relative_parent.parts):
        parsed = parse_folder_range(part, anchor)
        if parsed:
            return parsed
    return None


def source_range_for_records(path: Path, vats_dir: Path, days: Iterable[date]) -> SourceRange:
    day_list = list(days)
    if not day_list:
        raise ImportErrorWithHint(f"В файле нет записей звонков: {path}")
    actual_start = min(day_list)
    actual_end = max(day_list)
    declared = find_declared_range(path, vats_dir, actual_end)
    if declared:
        declared_start, declared_end = declared
        if actual_start < declared_start or actual_end > declared_end:
            raise ImportErrorWithHint(
                f"Даты звонков {actual_start:%d.%m.%Y}-{actual_end:%d.%m.%Y} не входят "
                f"в диапазон папки {declared_start:%d.%m.%Y}-{declared_end:%d.%m.%Y}: {path}",
            )
        return SourceRange(path=path, start=declared_start, end=declared_end)
    return SourceRange(path=path, start=actual_start, end=actual_end)


def source_range_for_summary(
    path: Path,
    vats_dir: Path,
    summary: BeelineSummaryRecord,
    fallback_date: date,
) -> SourceRange:
    anchor = summary.generated_on or fallback_date
    declared = find_declared_range(path, vats_dir, anchor)
    if not declared:
        raise ImportErrorWithHint(
            f"Для сводной выгрузки Билайна нужна папка с диапазоном дат, например 01.06-03.06: {path}",
        )
    start, end = declared
    if sprint_start_for_date(start) != sprint_start_for_date(end):
        raise ImportErrorWithHint(
            f"Сводная выгрузка Билайна не может пересекать спринты, потому что в ней нет дат отдельных звонков: {path}",
        )
    return SourceRange(path=path, start=start, end=end)


def ensure_non_overlapping(ranges: list[SourceRange], provider_name: str) -> None:
    ordered = sorted(ranges, key=lambda item: (item.start, item.end, str(item.path)))
    for previous, current in zip(ordered, ordered[1:]):
        if current.start <= previous.end:
            raise ImportErrorWithHint(
                f"Диапазоны {provider_name} пересекаются: "
                f"{previous.path} ({previous.start:%d.%m.%Y}-{previous.end:%d.%m.%Y}) и "
                f"{current.path} ({current.start:%d.%m.%Y}-{current.end:%d.%m.%Y}).",
            )


def csv_source_kind(path: Path) -> str:
    normalized = normalize_text(path.stem)
    if "эфир" in normalized or "efir" in normalized or "air" in normalized:
        return "air"
    if "звонк" in normalized or normalized in {"calls", "call count", "call counts"}:
        return "calls"
    if "calls export" in normalized or "calls_export" in normalized:
        return "combined"
    return ""


def discover_vats_files(vats_dir: Path) -> tuple[list[Path], list[Path], list[Path]]:
    megafon_files: list[Path] = []
    beeline_files: list[Path] = []
    csv_files: list[Path] = []
    if not vats_dir.exists():
        return megafon_files, beeline_files, csv_files

    for path in sorted(vats_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        normalized = normalize_text(path.stem)
        if path.suffix.lower() == ".csv":
            if csv_source_kind(path):
                csv_files.append(path)
            else:
                raise ImportErrorWithHint(
                    f"Не удалось определить тип CSV-файла '{path.name}'. "
                    "Используйте имя звонки.csv, эфир.csv или calls_export.csv.",
                )
        elif path.suffix.lower() == ".xlsx" and ("megafon" in normalized or "мегафон" in normalized):
            megafon_files.append(path)
        elif path.suffix.lower() == ".xls" and ("beeline" in normalized or "билайн" in normalized):
            beeline_files.append(path)
        elif path.suffix.lower() in {".xls", ".xlsx"}:
            raise ImportErrorWithHint(
                f"Не удалось определить оператора по имени файла '{path.name}'. "
                "Используйте имя megafon.xlsx или beeline.xls.",
            )
    return megafon_files, beeline_files, csv_files


def load_megafon_sources(paths: list[Path], vats_dir: Path) -> tuple[list[CallHistoryRecord], list[SourceRange]]:
    records: list[CallHistoryRecord] = []
    ranges: list[SourceRange] = []
    for path in paths:
        try:
            file_records = parse_megafon_history_records(path)
        except ImportErrorWithHint as exc:
            raise ImportErrorWithHint(f"Не удалось прочитать историю Мегафона {path}: {exc}") from exc
        ranges.append(source_range_for_records(path, vats_dir, (record.day for record in file_records)))
        records.extend(file_records)
    ensure_non_overlapping(ranges, "МегаФона")
    return records, ranges


def load_beeline_sources(
    paths: list[Path],
    vats_dir: Path,
    fallback_date: date,
) -> tuple[list[BeelineCallRecord], list[BeelineSummarySource], list[SourceRange]]:
    records: list[BeelineCallRecord] = []
    summaries: list[BeelineSummarySource] = []
    ranges: list[SourceRange] = []
    for path in paths:
        try:
            file_records = parse_beeline_records(path)
        except ImportErrorWithHint:
            file_records = []

        if file_records:
            source_range = source_range_for_records(path, vats_dir, (record.day for record in file_records))
            records.extend(file_records)
        else:
            summary = parse_beeline_summary(path)
            source_range = source_range_for_summary(path, vats_dir, summary, fallback_date)
            summaries.append(BeelineSummarySource(summary=summary, source_range=source_range))
        ranges.append(source_range)
    ensure_non_overlapping(ranges, "Билайна")
    return records, summaries, ranges


def parse_csv_call_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            pass
    return None


def parse_csv_duration_seconds(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    if re.fullmatch(r"\d+", text):
        return parse_int(text)
    return parse_duration_seconds(text)


def parse_csv_call_records(path: Path, source_kind: str) -> list[CsvCallRecord]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        if not reader.fieldnames:
            raise ImportErrorWithHint(f"В CSV нет заголовков: {path}")
        header_by_key = {normalize_text(header): header for header in reader.fieldnames}
        date_header = header_by_key.get("дата звонка")
        duration_header = header_by_key.get("длительность звонка")
        employee_header = header_by_key.get("менеджер")
        classification_header = header_by_key.get("классификация звонка")
        if not date_header or not employee_header or (source_kind != "calls" and not duration_header):
            if source_kind == "calls":
                required_columns = "'Дата звонка' и 'Менеджер'"
            else:
                required_columns = "'Дата звонка', 'Длительность звонка' и 'Менеджер'"
            raise ImportErrorWithHint(
                f"В CSV нужны колонки {required_columns}."
            )

        records: list[CsvCallRecord] = []
        for row in reader:
            current_date = parse_csv_call_date(row.get(date_header))
            employee = str(row.get(employee_header) or "").strip()
            if current_date is None or not employee:
                continue
            records.append(
                CsvCallRecord(
                    path=path,
                    day=current_date,
                    employee=employee,
                    duration_seconds=parse_csv_duration_seconds(row.get(duration_header)) if duration_header else 0,
                    classification=str(row.get(classification_header) or "").strip() if classification_header else "",
                    source_kind=source_kind,
                )
            )
    if not records:
        raise ImportErrorWithHint(f"В CSV не найдено строк звонков с датой и менеджером: {path}")
    return sorted(records, key=lambda record: (record.day, record.employee))


def csv_records_are_target_only(records: list[CsvCallRecord]) -> bool:
    return bool(records) and all(
        normalize_text(record.classification).startswith("целевой")
        for record in records
    )


def csv_records_include_non_target(records: list[CsvCallRecord]) -> bool:
    return any(
        not normalize_text(record.classification).startswith("целевой")
        for record in records
    )


def resolved_csv_source_kinds(records_by_path: dict[Path, list[CsvCallRecord]]) -> dict[Path, str]:
    resolved = {path: csv_source_kind(path) for path in records_by_path}
    paths_by_parent: dict[Path, list[Path]] = {}
    for path in records_by_path:
        paths_by_parent.setdefault(path.parent, []).append(path)

    for paths in paths_by_parent.values():
        calls_paths = [path for path in paths if resolved.get(path) == "calls"]
        air_paths = [path for path in paths if resolved.get(path) == "air"]
        if len(calls_paths) != 1 or len(air_paths) != 1:
            continue
        calls_path = calls_paths[0]
        air_path = air_paths[0]
        if (
            csv_records_are_target_only(records_by_path[calls_path])
            and csv_records_include_non_target(records_by_path[air_path])
        ):
            resolved[calls_path] = "air"
            resolved[air_path] = "calls"
    return resolved


def load_csv_sources(paths: list[Path], vats_dir: Path) -> tuple[list[CsvCallRecord], list[SourceRange]]:
    records_by_path: dict[Path, list[CsvCallRecord]] = {}
    ranges: list[SourceRange] = []
    for path in paths:
        source_kind = csv_source_kind(path)
        if not source_kind:
            continue
        try:
            file_records = parse_csv_call_records(path, source_kind)
        except ImportErrorWithHint as exc:
            raise ImportErrorWithHint(f"Не удалось прочитать CSV звонков {path}: {exc}") from exc
        records_by_path[path] = file_records

    resolved_kinds = resolved_csv_source_kinds(records_by_path)
    records: list[CsvCallRecord] = []
    for path, file_records in records_by_path.items():
        source_kind = resolved_kinds[path]
        if any(record.source_kind != source_kind for record in file_records):
            file_records = [replace(record, source_kind=source_kind) for record in file_records]
        ranges.append(source_range_for_records(path, vats_dir, (record.day for record in file_records)))
        records.extend(file_records)
    return records, ranges


def range_contains_day(source_range: SourceRange, value: date) -> bool:
    return source_range.start <= value <= source_range.end


def ranges_overlap(left: SourceRange, right: SourceRange) -> bool:
    return left.start <= right.end and right.start <= left.end


def csv_metric_kinds(record: CsvCallRecord) -> tuple[str, ...]:
    if record.source_kind == "calls":
        return ("calls",)
    if record.source_kind == "air":
        return ("air",)
    return ("calls", "air")


def csv_target_call_flags(classification: str) -> tuple[bool, bool]:
    normalized = normalize_text(classification)
    is_target = normalized.startswith("целевой")
    is_successful = normalized == "целевой результативный"
    return is_target, is_successful


def csv_call_is_completed(classification: str) -> bool:
    return normalize_text(classification) in COMPLETED_CALL_CLASSIFICATIONS


def csv_source_priority(record: CsvCallRecord, ranges_by_path: dict[Path, SourceRange]) -> tuple[date, date, int, str]:
    source_range = ranges_by_path.get(record.path)
    end = source_range.end if source_range else record.day
    start = source_range.start if source_range else record.day
    specificity = 1 if record.source_kind in {"calls", "air"} else 0
    return end, start, specificity, record.path.as_posix()


def preferred_csv_sources(records: list[CsvCallRecord], ranges: list[SourceRange]) -> dict[tuple[str, date], Path]:
    ranges_by_path = {source_range.path: source_range for source_range in ranges}
    preferred: dict[tuple[str, date], tuple[tuple[date, date, int, str], Path]] = {}
    for record in records:
        for metric_kind in csv_metric_kinds(record):
            key = (metric_kind, record.day)
            priority = csv_source_priority(record, ranges_by_path)
            current = preferred.get(key)
            if current is None or priority > current[0]:
                preferred[key] = (priority, record.path)
    return {key: path for key, (_priority, path) in preferred.items()}


def aggregate_csv_records(
    records: list[CsvCallRecord],
    name_map: dict[str, str],
    preferred_sources: dict[tuple[str, date], Path],
) -> tuple[list[dict[str, Any]], dict[str, int], set[Path], int, int]:
    by_week_mop: dict[tuple[date, str], dict[str, int]] = {}
    skipped_by_employee: dict[str, int] = {}
    used_paths: set[Path] = set()
    imported_call_count = 0
    imported_air_seconds = 0

    for record in records:
        mop_name = name_map.get(normalize_text(record.employee))
        if not mop_name:
            skipped_by_employee[record.employee] = skipped_by_employee.get(record.employee, 0) + 1
            continue
        use_calls = "calls" in csv_metric_kinds(record) and preferred_sources.get(("calls", record.day)) == record.path
        use_air = "air" in csv_metric_kinds(record) and preferred_sources.get(("air", record.day)) == record.path
        if not use_calls and not use_air:
            continue
        key = (sprint_start_for_date(record.day), mop_name)
        metrics = by_week_mop.setdefault(key, {})
        used_paths.add(record.path)
        if use_calls:
            metrics["callsFact"] = metrics.get("callsFact", 0) + 1
            metrics["crmCallsFact"] = metrics.get("crmCallsFact", 0) + 1
            if csv_call_is_completed(record.classification):
                metrics["completedCallsFact"] = metrics.get("completedCallsFact", 0) + 1
            is_target, is_successful = csv_target_call_flags(record.classification)
            if is_target:
                metrics["targetCallsFact"] = metrics.get("targetCallsFact", 0) + 1
                metrics["crmTargetCallsFact"] = metrics.get("crmTargetCallsFact", 0) + 1
            if is_successful:
                metrics["targetSuccessfulCallsFact"] = metrics.get("targetSuccessfulCallsFact", 0) + 1
                metrics["crmTargetSuccessfulCallsFact"] = metrics.get("crmTargetSuccessfulCallsFact", 0) + 1
            imported_call_count += 1
        if use_air:
            metrics["airTimeFactSeconds"] = metrics.get("airTimeFactSeconds", 0) + record.duration_seconds
            metrics["crmAirTimeFactSeconds"] = metrics.get("crmAirTimeFactSeconds", 0) + record.duration_seconds
            imported_air_seconds += record.duration_seconds

    rows: list[dict[str, Any]] = []
    for (week_start, mop_name), metrics in sorted(by_week_mop.items(), key=lambda item: (item[0][0], item[0][1])):
        row = empty_metric_row(week_start, mop_name=mop_name, mop_id="", manual_aggregate=False)
        row.update(metrics)
        row["airTimeFact"] = format_duration(row["airTimeFactSeconds"])
        row["callsSource"] = CRM_CALLS_SOURCE
        row["airTimeSource"] = CRM_CALLS_SOURCE
        rows.append(row)
    return rows, skipped_by_employee, used_paths, imported_call_count, imported_air_seconds


def aggregate_csv_daily_records(
    records: list[CsvCallRecord],
    name_map: dict[str, str],
    preferred_sources: dict[tuple[str, date], Path],
) -> list[dict[str, Any]]:
    by_day_mop: dict[tuple[date, str], dict[str, int]] = {}

    for record in records:
        mop_name = name_map.get(normalize_text(record.employee))
        if not mop_name:
            continue
        use_calls = "calls" in csv_metric_kinds(record) and preferred_sources.get(("calls", record.day)) == record.path
        use_air = "air" in csv_metric_kinds(record) and preferred_sources.get(("air", record.day)) == record.path
        if not use_calls and not use_air:
            continue
        key = (record.day, mop_name)
        metrics = by_day_mop.setdefault(key, {})
        if use_calls:
            metrics["callsFact"] = metrics.get("callsFact", 0) + 1
            metrics["crmCallsFact"] = metrics.get("crmCallsFact", 0) + 1
            if csv_call_is_completed(record.classification):
                metrics["completedCallsFact"] = metrics.get("completedCallsFact", 0) + 1
            is_target, is_successful = csv_target_call_flags(record.classification)
            if is_target:
                metrics["targetCallsFact"] = metrics.get("targetCallsFact", 0) + 1
                metrics["crmTargetCallsFact"] = metrics.get("crmTargetCallsFact", 0) + 1
            if is_successful:
                metrics["targetSuccessfulCallsFact"] = metrics.get("targetSuccessfulCallsFact", 0) + 1
                metrics["crmTargetSuccessfulCallsFact"] = metrics.get("crmTargetSuccessfulCallsFact", 0) + 1
        if use_air:
            metrics["airTimeFactSeconds"] = metrics.get("airTimeFactSeconds", 0) + record.duration_seconds
            metrics["crmAirTimeFactSeconds"] = metrics.get("crmAirTimeFactSeconds", 0) + record.duration_seconds

    rows: list[dict[str, Any]] = []
    for (current_date, mop_name), metrics in sorted(by_day_mop.items(), key=lambda item: (item[0][0], item[0][1])):
        week_start = sprint_start_for_date(current_date)
        row = empty_metric_row(week_start, mop_name=mop_name, mop_id="", manual_aggregate=False)
        row["date"] = current_date.isoformat()
        row["dateLabel"] = current_date.strftime("%d.%m.%Y")
        row.update(metrics)
        row["airTimeFact"] = format_duration(row["airTimeFactSeconds"])
        row["callsSource"] = CRM_CALLS_SOURCE
        row["airTimeSource"] = CRM_CALLS_SOURCE
        rows.append(row)
    return rows


def combine_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("weekStart", "")), str(row.get("mopName", "")))
        target = combined.get(key)
        if target is None:
            combined[key] = dict(row)
            continue
        for field in SUM_FIELDS:
            target[field] = int(target.get(field) or 0) + int(row.get(field) or 0)
        target["airTimeFact"] = format_duration(int(target.get("airTimeFactSeconds") or 0))
    return sorted(combined.values(), key=lambda row: (str(row.get("weekStart", "")), str(row.get("mopName", ""))))


def clear_existing_csv_call_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    csv_keys = {
        "callsFactBaseBeforeCrmCalls",
        "completedCallsFact",
        "targetCallsFactBaseBeforeCrmCalls",
        "targetSuccessfulCallsFactBaseBeforeCrmCalls",
        "airTimeFactSecondsBaseBeforeCrmCalls",
        "crmCallsFact",
        "crmTargetCallsFact",
        "crmTargetSuccessfulCallsFact",
        "crmAirTimeFactSeconds",
    }
    for row in rows:
        if row.get("manualSource") == CRM_CALLS_SOURCE:
            continue
        if row.get("callsSource") == CRM_CALLS_SOURCE:
            row["callsFact"] = int(row.get("callsFactBaseBeforeCrmCalls") or 0)
            row["targetCallsFact"] = int(row.get("targetCallsFactBaseBeforeCrmCalls") or 0)
            row["targetSuccessfulCallsFact"] = int(row.get("targetSuccessfulCallsFactBaseBeforeCrmCalls") or 0)
            row.pop("callsSource", None)
        if row.get("airTimeSource") == CRM_CALLS_SOURCE:
            row["airTimeFactSeconds"] = int(row.get("airTimeFactSecondsBaseBeforeCrmCalls") or 0)
            row["airTimeFact"] = format_duration(int(row.get("airTimeFactSeconds") or 0))
            row.pop("airTimeSource", None)
        for key in csv_keys:
            row.pop(key, None)
        cleaned.append(row)
    return cleaned


def merge_csv_call_rows(payload: dict[str, Any], csv_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_rows = clear_existing_csv_call_data(payload.get("baseRows", []))
    rows_by_key = {
        (str(row.get("weekStart", "")), str(row.get("mopName", ""))): row
        for row in base_rows
    }

    for import_row in csv_rows:
        key = (str(import_row["weekStart"]), str(import_row["mopName"]))
        row = rows_by_key.get(key)
        if row is None:
            row = empty_metric_row(
                date.fromisoformat(str(import_row["weekStart"])),
                mop_name=str(import_row["mopName"]),
                mop_id=str(import_row.get("mopId", "")),
                manual_aggregate=False,
            )
            base_rows.append(row)
            rows_by_key[key] = row

        base_calls = int(row.get("callsFact") or 0)
        base_target_calls = int(row.get("targetCallsFact") or 0)
        base_successful_target_calls = int(row.get("targetSuccessfulCallsFact") or 0)
        base_air = int(row.get("airTimeFactSeconds") or 0)
        row["callsFactBaseBeforeCrmCalls"] = base_calls
        row["targetCallsFactBaseBeforeCrmCalls"] = base_target_calls
        row["targetSuccessfulCallsFactBaseBeforeCrmCalls"] = base_successful_target_calls
        row["airTimeFactSecondsBaseBeforeCrmCalls"] = base_air
        row["callsFact"] = base_calls + int(import_row.get("callsFact") or 0)
        row["completedCallsFact"] = int(import_row.get("completedCallsFact") or 0)
        row["targetCallsFact"] = base_target_calls + int(import_row.get("targetCallsFact") or 0)
        row["targetSuccessfulCallsFact"] = (
            base_successful_target_calls + int(import_row.get("targetSuccessfulCallsFact") or 0)
        )
        row["airTimeFactSeconds"] = base_air + int(import_row.get("airTimeFactSeconds") or 0)
        row["airTimeFact"] = format_duration(int(row["airTimeFactSeconds"]))
        row["callsSource"] = CRM_CALLS_SOURCE
        row["airTimeSource"] = CRM_CALLS_SOURCE
        row["crmCallsFact"] = int(import_row.get("crmCallsFact") or 0)
        row["crmTargetCallsFact"] = int(import_row.get("crmTargetCallsFact") or 0)
        row["crmTargetSuccessfulCallsFact"] = int(import_row.get("crmTargetSuccessfulCallsFact") or 0)
        row["crmAirTimeFactSeconds"] = int(import_row.get("crmAirTimeFactSeconds") or 0)
        row.pop("sharedPlanOnlyRow", None)

    payload["baseRows"] = sorted(
        base_rows,
        key=lambda row: (str(row.get("weekStart", "")), str(row.get("mopName", ""))),
    )
    return payload["baseRows"]


def merge_csv_daily_call_rows(payload: dict[str, Any], csv_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    daily_rows = clear_existing_csv_call_data(payload.get("dailyRows", []))
    rows_by_key = {
        (str(row.get("date", "")), str(row.get("mopName", ""))): row
        for row in daily_rows
    }

    for import_row in csv_rows:
        key = (str(import_row.get("date", "")), str(import_row["mopName"]))
        row = rows_by_key.get(key)
        if row is None:
            row = empty_metric_row(
                date.fromisoformat(str(import_row["weekStart"])),
                mop_name=str(import_row["mopName"]),
                mop_id=str(import_row.get("mopId", "")),
                manual_aggregate=False,
            )
            row["date"] = str(import_row.get("date", ""))
            row["dateLabel"] = str(import_row.get("dateLabel", ""))
            daily_rows.append(row)
            rows_by_key[key] = row

        base_calls = int(row.get("callsFact") or 0)
        base_target_calls = int(row.get("targetCallsFact") or 0)
        base_successful_target_calls = int(row.get("targetSuccessfulCallsFact") or 0)
        base_air = int(row.get("airTimeFactSeconds") or 0)
        row["callsFactBaseBeforeCrmCalls"] = base_calls
        row["targetCallsFactBaseBeforeCrmCalls"] = base_target_calls
        row["targetSuccessfulCallsFactBaseBeforeCrmCalls"] = base_successful_target_calls
        row["airTimeFactSecondsBaseBeforeCrmCalls"] = base_air
        row["callsFact"] = base_calls + int(import_row.get("callsFact") or 0)
        row["completedCallsFact"] = int(import_row.get("completedCallsFact") or 0)
        row["targetCallsFact"] = base_target_calls + int(import_row.get("targetCallsFact") or 0)
        row["targetSuccessfulCallsFact"] = (
            base_successful_target_calls + int(import_row.get("targetSuccessfulCallsFact") or 0)
        )
        row["airTimeFactSeconds"] = base_air + int(import_row.get("airTimeFactSeconds") or 0)
        row["airTimeFact"] = format_duration(int(row["airTimeFactSeconds"]))
        row["callsSource"] = CRM_CALLS_SOURCE
        row["airTimeSource"] = CRM_CALLS_SOURCE
        row["crmCallsFact"] = int(import_row.get("crmCallsFact") or 0)
        row["crmTargetCallsFact"] = int(import_row.get("crmTargetCallsFact") or 0)
        row["crmTargetSuccessfulCallsFact"] = int(import_row.get("crmTargetSuccessfulCallsFact") or 0)
        row["crmAirTimeFactSeconds"] = int(import_row.get("crmAirTimeFactSeconds") or 0)
        row.pop("sharedPlanOnlyRow", None)

    payload["dailyRows"] = sorted(
        daily_rows,
        key=lambda row: (str(row.get("date", "")), str(row.get("mopName", ""))),
    )
    return payload["dailyRows"]


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def range_metadata(source_range: SourceRange) -> dict[str, str]:
    return {
        "fileName": display_path(source_range.path),
        "from": source_range.start.isoformat(),
        "to": source_range.end.isoformat(),
    }


def russian_count(value: int, one: str, few: str, many: str) -> str:
    remainder_100 = value % 100
    remainder_10 = value % 10
    if 11 <= remainder_100 <= 14:
        word = many
    elif remainder_10 == 1:
        word = one
    elif 2 <= remainder_10 <= 4:
        word = few
    else:
        word = many
    return f"{value} {word}"


def replace_vats_warnings(
    payload: dict[str, Any],
    *,
    csv_file_count: int,
    csv_skipped: dict[str, int],
    megafon_file_count: int,
    megafon_skipped: dict[str, int],
    beeline_detailed_count: int,
    beeline_summary_count: int,
    beeline_skipped: dict[str, int],
) -> None:
    warnings = [
        warning
        for warning in payload.get("warnings", [])
        if not str(warning).startswith("МегаФон ВАТС:")
        and not str(warning).startswith("Билайн:")
        and not str(warning).startswith(CRM_CALLS_WARNING_PREFIX)
        and not str(warning).startswith("Звонки не посчитаны:")
    ]
    if csv_file_count:
        warnings.append(
            f"{CRM_CALLS_WARNING_PREFIX} звонки и эфир импортированы из "
            f"{russian_count(csv_file_count, 'CSV-файла', 'CSV-файлов', 'CSV-файлов')} по МОПам.",
        )
        skipped_total = sum(csv_skipped.values())
        if skipped_total:
            warnings.append(f"{CRM_CALLS_WARNING_PREFIX} пропущено {skipped_total} звонков менеджеров вне списка МОП.")
    if megafon_file_count:
        warnings.append(
            "МегаФон ВАТС: звонки и эфир импортированы из "
            f"{russian_count(megafon_file_count, 'файла', 'файлов', 'файлов')} по сотрудникам.",
        )
        skipped_total = sum(megafon_skipped.values())
        if skipped_total:
            warnings.append(f"МегаФон ВАТС: пропущено {skipped_total} звонков сотрудников вне списка МОП.")
    if beeline_detailed_count:
        warnings.append(
            "Билайн: звонки и эфир импортированы из "
            f"{russian_count(beeline_detailed_count, 'файла', 'файлов', 'файлов')} по абонентам.",
        )
        skipped_total = sum(beeline_skipped.values())
        if skipped_total:
            warnings.append(f"Билайн: пропущено {skipped_total} звонков абонентов вне списка МОП.")
    if beeline_summary_count:
        summary_label = russian_count(beeline_summary_count, "сводный файл", "сводных файла", "сводных файлов")
        summary_verb = "добавлен" if beeline_summary_count == 1 else "добавлены"
        warnings.append(f"Билайн: {summary_label} {summary_verb} только в общий итог без разбивки по МОП.")
    payload["warnings"] = warnings


def main() -> int:
    try:
        args = parse_args()
        vats_dir = Path(args.vats_dir)
        data_path = Path(args.dashboard_data)
        if not data_path.exists():
            raise ImportErrorWithHint(f"Файл данных dashboard не найден: {data_path}")

        megafon_files, beeline_files, csv_files = discover_vats_files(vats_dir)
        if not args.no_legacy:
            if LEGACY_MEGAFON_HISTORY.exists():
                megafon_files.insert(0, LEGACY_MEGAFON_HISTORY)
            if LEGACY_BEELINE_STAT.exists():
                beeline_files.insert(0, LEGACY_BEELINE_STAT)
        if not megafon_files and not beeline_files and not csv_files:
            raise ImportErrorWithHint(f"В {vats_dir} и manual-data не найдено файлов ВАТС.")

        payload = json.loads(data_path.read_text(encoding="utf-8"))
        report_from = parse_payload_date(payload, "from")
        report_to = parse_payload_date(payload, "to")
        fallback_date = report_to or date.today()

        csv_records, csv_ranges = load_csv_sources(csv_files, vats_dir)
        megafon_records, megafon_ranges = load_megafon_sources(megafon_files, vats_dir)
        beeline_records, beeline_summaries, beeline_ranges = load_beeline_sources(
            beeline_files,
            vats_dir,
            fallback_date,
        )
        if csv_ranges:
            megafon_records = [
                record
                for record in megafon_records
                if not any(range_contains_day(source_range, record.day) for source_range in csv_ranges)
            ]
            beeline_records = [
                record
                for record in beeline_records
                if not any(range_contains_day(source_range, record.day) for source_range in csv_ranges)
            ]
            beeline_summaries = [
                summary_source
                for summary_source in beeline_summaries
                if not any(ranges_overlap(summary_source.source_range, source_range) for source_range in csv_ranges)
            ]

        all_end_dates = [source_range.end for source_range in [*megafon_ranges, *beeline_ranges, *csv_ranges]]
        upper_bound = max([fallback_date, *all_end_dates])
        payload.setdefault("report", {})["to"] = upper_bound.isoformat()

        # Remove both providers before adding them again. This keeps repeated local imports idempotent.
        payload["baseRows"] = clear_existing_beeline_data(payload.get("baseRows", []))
        payload["baseRows"] = clear_existing_megafon_data(payload.get("baseRows", []))
        payload["baseRows"] = clear_existing_csv_call_data(payload.get("baseRows", []))
        payload["dailyRows"] = clear_existing_csv_call_data(payload.get("dailyRows", []))
        name_map = canonical_mop_names(payload)
        imported_rows: list[dict[str, Any]] = []

        csv_records = filter_records_by_window(csv_records, report_from, upper_bound)
        csv_preferred_sources = preferred_csv_sources(csv_records, csv_ranges)
        csv_rows, csv_skipped, csv_used_paths, csv_imported_calls, csv_imported_air = aggregate_csv_records(
            csv_records,
            name_map,
            csv_preferred_sources,
        )
        csv_used_ranges = [source_range for source_range in csv_ranges if source_range.path in csv_used_paths]
        if csv_rows:
            merge_csv_call_rows(payload, csv_rows)
            csv_daily_rows = aggregate_csv_daily_records(csv_records, name_map, csv_preferred_sources)
            merge_csv_daily_call_rows(payload, csv_daily_rows)
            imported_rows.extend(csv_rows)

        megafon_records = filter_records_by_window(megafon_records, report_from, upper_bound)
        megafon_rows, megafon_skipped = aggregate_history_records(megafon_records, name_map)
        if megafon_rows:
            merge_history_rows(payload, megafon_rows)
            imported_rows.extend(megafon_rows)

        beeline_records = filter_records_by_window(beeline_records, report_from, upper_bound)
        beeline_rows, beeline_skipped = aggregate_beeline_records(beeline_records, name_map)
        for summary_source in beeline_summaries:
            if report_from and summary_source.source_range.end < report_from:
                continue
            beeline_rows.append(
                aggregate_beeline_summary(
                    summary_source.summary,
                    sprint_start_for_date(summary_source.source_range.start),
                ),
            )
        beeline_rows = combine_rows(beeline_rows)
        if beeline_rows:
            merge_beeline_rows(payload, beeline_rows)
            imported_rows.extend(beeline_rows)

        imported_at = datetime.now().isoformat(timespec="seconds")
        manual_imports = payload.setdefault("manualImports", {})
        manual_imports[CRM_CALLS_SOURCE] = {
            "mode": "vats_directory",
            "importedAt": imported_at,
            "files": [range_metadata(source_range) for source_range in csv_used_ranges],
            "fileCount": len(csv_used_ranges),
            "recordCount": len(csv_records),
            "importedCallCount": csv_imported_calls,
            "importedAirTimeSeconds": csv_imported_air,
            "skippedCallCount": sum(csv_skipped.values()),
            "skippedEmployees": csv_skipped,
            "hasMopBreakdown": True,
            "hasAirTime": True,
            "durationUnit": "seconds",
        }
        manual_imports[MEGAFON_SOURCE] = {
            "mode": "vats_directory",
            "importedAt": imported_at,
            "files": [range_metadata(source_range) for source_range in megafon_ranges],
            "fileCount": len(megafon_ranges),
            "recordCount": len(megafon_records),
            "importedCallCount": sum(int(row.get("callsFact") or 0) for row in megafon_rows),
            "importedAirTimeSeconds": sum(int(row.get("airTimeFactSeconds") or 0) for row in megafon_rows),
            "skippedCallCount": sum(megafon_skipped.values()),
            "skippedEmployees": megafon_skipped,
            "hasMopBreakdown": True,
            "hasAirTime": True,
        }
        manual_imports[BEELINE_SOURCE] = {
            "mode": "vats_directory",
            "importedAt": imported_at,
            "files": [range_metadata(source_range) for source_range in beeline_ranges],
            "fileCount": len(beeline_ranges),
            "detailedFileCount": len(beeline_ranges) - len(beeline_summaries),
            "summaryFileCount": len(beeline_summaries),
            "recordCount": len(beeline_records) + sum(source.summary.total_calls for source in beeline_summaries),
            "importedCallCount": sum(int(row.get("callsFact") or 0) for row in beeline_rows),
            "importedAirTimeSeconds": sum(int(row.get("airTimeFactSeconds") or 0) for row in beeline_rows),
            "skippedCallCount": sum(beeline_skipped.values()),
            "skippedEmployees": beeline_skipped,
            "hasMopBreakdown": bool(beeline_records),
            "hasAggregateSummary": bool(beeline_summaries),
            "hasAirTime": True,
        }

        replace_vats_warnings(
            payload,
            csv_file_count=len(csv_used_ranges),
            csv_skipped=csv_skipped,
            megafon_file_count=len(megafon_ranges) if megafon_rows else 0,
            megafon_skipped=megafon_skipped,
            beeline_detailed_count=(len(beeline_ranges) - len(beeline_summaries)) if beeline_rows else 0,
            beeline_summary_count=len(beeline_summaries),
            beeline_skipped=beeline_skipped,
        )
        payload["generatedAt"] = imported_at
        update_filters(payload, imported_rows)
        recompute_totals(payload)
        update_overview(payload)
        write_payload(payload, data_path)

        print(f"Imported CRM CSV calls: {manual_imports[CRM_CALLS_SOURCE]['importedCallCount']}")
        print(f"Imported CRM CSV air time: {format_duration(manual_imports[CRM_CALLS_SOURCE]['importedAirTimeSeconds'])}")
        print(f"Imported MegaFon calls: {manual_imports[MEGAFON_SOURCE]['importedCallCount']}")
        print(f"Imported MegaFon air time: {format_duration(manual_imports[MEGAFON_SOURCE]['importedAirTimeSeconds'])}")
        print(f"Imported Beeline calls: {manual_imports[BEELINE_SOURCE]['importedCallCount']}")
        print(f"Imported Beeline air time: {format_duration(manual_imports[BEELINE_SOURCE]['importedAirTimeSeconds'])}")
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
