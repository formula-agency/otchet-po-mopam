from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
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
    filter_records_by_window,
    format_duration,
    merge_history_rows,
    normalize_text,
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
RANGE_PATTERN = re.compile(
    r"^\s*(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*-\s*"
    r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*$",
)
SUM_FIELDS = {
    "callsFact",
    "airTimeFactSeconds",
    "beelineCallsFact",
    "beelineAirTimeFactSeconds",
    "beelineAnsweredCalls",
    "beelineIncomingCalls",
    "beelineMissedCalls",
    "beelineOutgoingCalls",
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


def discover_vats_files(vats_dir: Path) -> tuple[list[Path], list[Path]]:
    megafon_files: list[Path] = []
    beeline_files: list[Path] = []
    if not vats_dir.exists():
        return megafon_files, beeline_files

    for path in sorted(vats_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        normalized = normalize_text(path.stem)
        if path.suffix.lower() == ".xlsx" and ("megafon" in normalized or "мегафон" in normalized):
            megafon_files.append(path)
        elif path.suffix.lower() == ".xls" and ("beeline" in normalized or "билайн" in normalized):
            beeline_files.append(path)
        elif path.suffix.lower() in {".xls", ".xlsx"}:
            raise ImportErrorWithHint(
                f"Не удалось определить оператора по имени файла '{path.name}'. "
                "Используйте имя megafon.xlsx или beeline.xls.",
            )
    return megafon_files, beeline_files


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
        and not str(warning).startswith("Звонки не посчитаны:")
    ]
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

        megafon_files, beeline_files = discover_vats_files(vats_dir)
        if not args.no_legacy:
            if LEGACY_MEGAFON_HISTORY.exists():
                megafon_files.insert(0, LEGACY_MEGAFON_HISTORY)
            if LEGACY_BEELINE_STAT.exists():
                beeline_files.insert(0, LEGACY_BEELINE_STAT)
        if not megafon_files and not beeline_files:
            raise ImportErrorWithHint(f"В {vats_dir} и manual-data не найдено файлов ВАТС.")

        payload = json.loads(data_path.read_text(encoding="utf-8"))
        report_from = parse_payload_date(payload, "from")
        report_to = parse_payload_date(payload, "to")
        fallback_date = report_to or date.today()

        megafon_records, megafon_ranges = load_megafon_sources(megafon_files, vats_dir)
        beeline_records, beeline_summaries, beeline_ranges = load_beeline_sources(
            beeline_files,
            vats_dir,
            fallback_date,
        )

        all_end_dates = [source_range.end for source_range in [*megafon_ranges, *beeline_ranges]]
        upper_bound = max([fallback_date, *all_end_dates])
        payload.setdefault("report", {})["to"] = upper_bound.isoformat()

        # Remove both providers before adding them again. This keeps repeated local imports idempotent.
        payload["baseRows"] = clear_existing_beeline_data(payload.get("baseRows", []))
        payload["baseRows"] = clear_existing_megafon_data(payload.get("baseRows", []))
        name_map = canonical_mop_names(payload)
        imported_rows: list[dict[str, Any]] = []

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
            megafon_file_count=len(megafon_ranges),
            megafon_skipped=megafon_skipped,
            beeline_detailed_count=len(beeline_ranges) - len(beeline_summaries),
            beeline_summary_count=len(beeline_summaries),
            beeline_skipped=beeline_skipped,
        )
        payload["generatedAt"] = imported_at
        update_filters(payload, imported_rows)
        recompute_totals(payload)
        update_overview(payload)
        write_payload(payload, data_path)

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
