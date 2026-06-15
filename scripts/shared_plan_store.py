from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from import_megafon_calls import (
    METRIC_ZEROES,
    empty_metric_row,
    format_duration,
    normalize_text,
    parse_int,
    read_xlsx_rows,
    update_filters,
    update_overview,
    write_payload,
)


STORE_SCHEMA_VERSION = 1
SUBMISSION_SCHEMA_VERSION = 1
SUBMISSION_MARKER = "MOP_REPORT_SHARED_PLAN_V1"
SHARED_PLAN_SOURCE = "shared_upload"
AGGREGATE_PLAN_NAME = "Общий план"
DEFAULT_STORE_PATH = Path("manual-data/shared-plans.json")
DEFAULT_DASHBOARD_DATA_PATH = Path("dashboard/data/mop-report-data.json")
ALLOWED_AUTHOR_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
MOP_NAMES = (
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
MOP_IDS_BY_NAME = {
    "Погребинский Артем": "39",
    "Черткова Ирина": "159",
    "Газисова Мария": "160",
    "Попова Олеся": "161",
    "Губайдулина Заррина": "174",
    "Камболин Александр": "189",
    "Тончу Ростислав": "190",
    "Жуков Лев": "194",
    "Попова Юлия": "195",
    "Гавриленко Елена": "197",
}
PLAN_FIELDS = (
    "salesPlan",
    "meetingsPlan",
    "reservationsPlan",
    "approvedMortgagesPlan",
    "airTimePlanSeconds",
)
BASE_PLAN_FIELDS = {field: f"{field}BaseBeforeShared" for field in PLAN_FIELDS}
PLAN_HEADER_ALIASES = {
    "mopName": {"моп", "менеджер"},
    "salesPlan": {"продажи", "план продаж", "план по продажам", "сделки", "план сделок", "план по сделкам"},
    "meetingsPlan": {"встречи", "проведенные встречи", "план встреч"},
    "reservationsPlan": {"брони", "созданные брони", "план броней"},
    "approvedMortgagesPlan": {"ипотеки", "одобренные ипотеки", "план ипотек"},
    "airTimePlanSeconds": {"эфир", "целевое эфирное время", "план эфирного времени"},
}
AGGREGATE_PLAN_ALIASES = {"общий план", "общий", "итого", "все мопы"}


class SharedPlanError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage shared MOP plans used by every dashboard session.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    from_xlsx = subparsers.add_parser("from-xlsx", help="Import a plan workbook into the shared plan store.")
    from_xlsx.add_argument("xlsx_file")
    from_xlsx.add_argument("--store", default=str(DEFAULT_STORE_PATH))

    publish_event = subparsers.add_parser("publish-event", help="Publish a plan from a GitHub issue event payload.")
    publish_event.add_argument("event_file")
    publish_event.add_argument("--store", default=str(DEFAULT_STORE_PATH))

    apply_command = subparsers.add_parser("apply", help="Apply all shared plans to dashboard data.")
    apply_command.add_argument("--store", default=str(DEFAULT_STORE_PATH))
    apply_command.add_argument("--dashboard-data", default=str(DEFAULT_DASHBOARD_DATA_PATH))
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ").strip()).lower().replace("ё", "е")


def canonical_mop_name(value: Any) -> str:
    key = normalize_name(value)
    if key in AGGREGATE_PLAN_ALIASES:
        return AGGREGATE_PLAN_NAME
    return next((name for name in MOP_NAMES if normalize_name(name) == key), "")


def parse_month(value: Any) -> str:
    if isinstance(value, (int, float)) or re.fullmatch(r"\d+(?:[.,]\d+)?", str(value or "").strip()):
        try:
            serial = float(str(value).replace(",", "."))
            parsed = datetime(1899, 12, 30) + timedelta(days=serial)
            return parsed.strftime("%Y-%m")
        except (ValueError, OverflowError):
            pass

    text = str(value or "").strip()
    for pattern, order in (
        (r"^(\d{4})-(\d{1,2})(?:-\d{1,2})?", "ym"),
        (r"^\d{1,2}[./-](\d{1,2})[./-](\d{4})$", "my"),
    ):
        match = re.match(pattern, text)
        if not match:
            continue
        if order == "ym":
            year, month = int(match.group(1)), int(match.group(2))
        else:
            month, year = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    raise SharedPlanError("Не найден корректный месяц плана.")


def parse_plan_number(value: Any) -> int:
    text = str(value or "").strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not text:
        return 0
    try:
        return max(0, round(float(text)))
    except ValueError:
        return 0


def parse_plan_duration_seconds(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    match = re.fullmatch(r"(\d{1,5}):(\d{2})(?::(\d{2}))?", text)
    if match:
        first, second, third = match.groups()
        if third is not None:
            return int(first) * 3600 + int(second) * 60 + int(third)
        return int(first) * 60 + int(second)
    try:
        numeric = float(text.replace(",", "."))
    except ValueError:
        return 0
    if 0 <= numeric < 1:
        return round(numeric * 86400)
    return max(0, round(numeric * 60))


def read_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": STORE_SCHEMA_VERSION, "updatedAt": "", "months": {}}
    try:
        store = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SharedPlanError(f"Не удалось прочитать хранилище планов: {exc}") from exc
    if not isinstance(store.get("months"), dict):
        raise SharedPlanError("Хранилище планов имеет неверный формат.")
    store["schemaVersion"] = STORE_SCHEMA_VERSION
    return store


def write_store(path: Path, store: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(store, ensure_ascii=False, indent=2)}\n", encoding="utf-8")


def find_month_in_rows(rows: list[list[str]]) -> str:
    month_labels = {"месяц", "дата плана", "период плана", "план на"}
    for row in rows[:25]:
        for index, value in enumerate(row[:8]):
            if normalize_text(value) not in month_labels:
                continue
            for candidate in row[index + 1 : index + 5]:
                try:
                    return parse_month(candidate)
                except SharedPlanError:
                    pass
    for row in rows[:25]:
        for value in row[:8]:
            try:
                return parse_month(value)
            except SharedPlanError:
                pass
    raise SharedPlanError("Не найден месяц плана.")


def find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    for row_index, row in enumerate(rows[:40]):
        mapping: dict[str, int] = {}
        for column_index, value in enumerate(row):
            normalized = normalize_text(value)
            for field, aliases in PLAN_HEADER_ALIASES.items():
                if normalized in aliases:
                    mapping[field] = column_index
        if "mopName" in mapping and any(field in mapping for field in PLAN_FIELDS):
            return row_index, mapping
    raise SharedPlanError("Не найдена строка заголовков плана.")


def cell(row: list[Any], index: int | None) -> Any:
    if index is None or index >= len(row):
        return ""
    return row[index]


def normalize_plan_entry(raw: dict[str, Any]) -> dict[str, Any]:
    mop_name = canonical_mop_name(raw.get("mopName"))
    if not mop_name:
        raise SharedPlanError(f"Неизвестный МОП в плане: {raw.get('mopName')}")
    aggregate_plan = mop_name == AGGREGATE_PLAN_NAME
    requested_fields = raw.get("aggregatePlanFields") if aggregate_plan else None
    aggregate_fields = [
        field for field in PLAN_FIELDS if not requested_fields or field in requested_fields
    ]
    entry = {
        "mopName": mop_name,
        "aggregatePlan": aggregate_plan,
        "salesPlan": parse_plan_number(raw.get("salesPlan")),
        "meetingsPlan": parse_plan_number(raw.get("meetingsPlan")),
        "reservationsPlan": parse_plan_number(raw.get("reservationsPlan")),
        "approvedMortgagesPlan": parse_plan_number(raw.get("approvedMortgagesPlan")),
        "airTimePlanSeconds": parse_plan_number(raw.get("airTimePlanSeconds")),
    }
    if aggregate_plan:
        entry["aggregatePlanFields"] = aggregate_fields
    return entry


def workbook_submission(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SharedPlanError(f"Файл не найден: {path}")
    sheets = read_xlsx_rows(path)
    sheet_name = next((name for name in sheets if normalize_text(name) == "сводная за месяц"), "")
    if not sheet_name:
        raise SharedPlanError('Не найден лист "Сводная за месяц".')
    rows = sheets[sheet_name]
    month = find_month_in_rows(rows)
    header_index, mapping = find_header(rows)
    plans: list[dict[str, Any]] = []
    skipped_names: list[str] = []
    for row in rows[header_index + 1 :]:
        raw_name = str(cell(row, mapping.get("mopName")) or "").strip()
        if not raw_name:
            continue
        mop_name = canonical_mop_name(raw_name)
        if not mop_name:
            skipped_names.append(raw_name)
            continue
        aggregate_plan = mop_name == AGGREGATE_PLAN_NAME
        aggregate_fields = [
            field for field in PLAN_FIELDS if field in mapping and str(cell(row, mapping.get(field)) or "").strip()
        ]
        if aggregate_plan and not aggregate_fields:
            continue
        raw_plan = {
            "mopName": mop_name,
            "aggregatePlanFields": aggregate_fields,
            "salesPlan": cell(row, mapping.get("salesPlan")),
            "meetingsPlan": cell(row, mapping.get("meetingsPlan")),
            "reservationsPlan": cell(row, mapping.get("reservationsPlan")),
            "approvedMortgagesPlan": cell(row, mapping.get("approvedMortgagesPlan")),
            "airTimePlanSeconds": parse_plan_duration_seconds(cell(row, mapping.get("airTimePlanSeconds"))),
        }
        plans.append(normalize_plan_entry(raw_plan))

    if not plans:
        raise SharedPlanError("В файле не найден план по МОПам.")

    manager_count = len({plan["mopName"] for plan in plans if not plan["aggregatePlan"]})
    return {
        "schemaVersion": SUBMISSION_SCHEMA_VERSION,
        "action": "upsert",
        "fileName": path.name,
        "month": month,
        "managerCount": manager_count,
        "hasAggregatePlan": any(plan["aggregatePlan"] for plan in plans),
        "skippedNames": sorted(set(skipped_names)),
        "plans": plans,
    }


def normalize_submission(raw: dict[str, Any]) -> dict[str, Any]:
    if int(raw.get("schemaVersion") or 0) != SUBMISSION_SCHEMA_VERSION:
        raise SharedPlanError("Неподдерживаемая версия данных плана.")
    action = str(raw.get("action") or "").strip().lower()
    if action not in {"upsert", "remove"}:
        raise SharedPlanError("Неподдерживаемое действие с планом.")
    month = parse_month(raw.get("month"))
    if action == "remove":
        return {"schemaVersion": SUBMISSION_SCHEMA_VERSION, "action": action, "month": month}

    raw_plans = raw.get("plans")
    if not isinstance(raw_plans, list) or not raw_plans:
        raise SharedPlanError("В публикации нет строк плана.")
    plans = [normalize_plan_entry(plan) for plan in raw_plans if isinstance(plan, dict)]
    if not plans:
        raise SharedPlanError("В публикации нет корректных строк плана.")
    names = [plan["mopName"] for plan in plans]
    if len(names) != len(set(names)):
        raise SharedPlanError("В публикации есть повторяющиеся строки МОП.")
    manager_count = len({plan["mopName"] for plan in plans if not plan["aggregatePlan"]})
    return {
        "schemaVersion": SUBMISSION_SCHEMA_VERSION,
        "action": action,
        "fileName": str(raw.get("fileName") or "Загруженный план").strip()[:200],
        "month": month,
        "managerCount": manager_count,
        "hasAggregatePlan": any(plan["aggregatePlan"] for plan in plans),
        "skippedNames": [str(name)[:200] for name in raw.get("skippedNames", []) if str(name).strip()],
        "plans": plans,
    }


def apply_submission(store: dict[str, Any], submission: dict[str, Any]) -> None:
    month = submission["month"]
    months = store.setdefault("months", {})
    if submission["action"] == "remove":
        months.pop(month, None)
    else:
        months[month] = {
            "fileName": submission["fileName"],
            "publishedAt": utc_now(),
            "managerCount": submission["managerCount"],
            "hasAggregatePlan": submission["hasAggregatePlan"],
            "skippedNames": submission["skippedNames"],
            "plans": submission["plans"],
        }
    store["schemaVersion"] = STORE_SCHEMA_VERSION
    store["updatedAt"] = utc_now()


def submission_from_issue_event(path: Path) -> dict[str, Any]:
    try:
        event = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SharedPlanError(f"Не удалось прочитать событие GitHub: {exc}") from exc
    issue = event.get("issue") or {}
    association = str(issue.get("author_association") or "").upper()
    if association not in ALLOWED_AUTHOR_ASSOCIATIONS:
        raise SharedPlanError("Публиковать план могут только владельцы и участники репозитория.")
    body = str(issue.get("body") or "")
    match = re.search(
        rf"<!--\s*{re.escape(SUBMISSION_MARKER)}\s*(\{{.*?\}})\s*-->",
        body,
        flags=re.DOTALL,
    )
    if not match:
        raise SharedPlanError("В задаче GitHub не найдены данные плана.")
    try:
        raw_submission = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise SharedPlanError(f"Данные плана в задаче GitHub повреждены: {exc}") from exc
    return normalize_submission(raw_submission)


def month_start(month: str) -> date:
    return datetime.strptime(f"{month}-01", "%Y-%m-%d").date()


def month_end(current: date) -> date:
    if current.month == 12:
        return date(current.year, 12, 31)
    return date(current.year, current.month + 1, 1) - timedelta(days=1)


def sprint_starts(month: str) -> list[date]:
    start = month_start(month)
    return [start.replace(day=day) for day in (1, 8, 15, 22)]


def split_monthly_value(value: Any) -> list[int]:
    total = max(0, parse_int(value))
    base = total // 4
    return [base, base, base, base + total - base * 4]


def clear_existing_shared_plans(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        if row.get("sharedPlanOnlyRow"):
            continue
        if row.get("planSource") == SHARED_PLAN_SOURCE:
            for field, base_field in BASE_PLAN_FIELDS.items():
                row[field] = parse_int(row.get(base_field))
                row.pop(base_field, None)
            row["airTimePlan"] = format_duration(parse_int(row.get("airTimePlanSeconds")))
            row.pop("planSource", None)
            row.pop("aggregatePlan", None)
            row.pop("aggregatePlanFields", None)
        cleaned.append(row)
    return cleaned


def build_shared_plan_rows(store: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for month, month_plan in sorted(store.get("months", {}).items()):
        for plan in month_plan.get("plans", []):
            mop_name = str(plan.get("mopName") or "")
            aggregate_plan = bool(plan.get("aggregatePlan"))
            split_values = {field: split_monthly_value(plan.get(field)) for field in PLAN_FIELDS}

            for sprint_index, week_start in enumerate(sprint_starts(month)):
                row = empty_metric_row(
                    week_start,
                    mop_name=mop_name,
                    mop_id=MOP_IDS_BY_NAME.get(mop_name, ""),
                    manual_aggregate=False,
                )
                for field in PLAN_FIELDS:
                    row[field] = split_values[field][sprint_index]
                row["airTimePlan"] = format_duration(row["airTimePlanSeconds"])
                row["planSource"] = SHARED_PLAN_SOURCE
                row["sharedPlanOnlyRow"] = True
                if aggregate_plan:
                    row["manualAggregate"] = True
                    row["aggregatePlan"] = True
                    row["aggregatePlanFields"] = plan.get("aggregatePlanFields") or list(PLAN_FIELDS)
                rows.append(row)
    return rows


def merge_shared_plan_rows(payload: dict[str, Any], shared_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_rows = clear_existing_shared_plans(payload.get("baseRows", []))
    rows_by_key = {
        (str(row.get("weekStart", "")), normalize_name(row.get("mopName"))): row
        for row in base_rows
    }
    for shared_row in shared_rows:
        key = (str(shared_row["weekStart"]), normalize_name(shared_row["mopName"]))
        row = rows_by_key.get(key)
        if row is None:
            base_rows.append(shared_row)
            rows_by_key[key] = shared_row
            continue
        for field, base_field in BASE_PLAN_FIELDS.items():
            row[base_field] = parse_int(row.get(field))
            row[field] = parse_int(shared_row.get(field))
        row["airTimePlan"] = format_duration(row["airTimePlanSeconds"])
        row["planSource"] = SHARED_PLAN_SOURCE

    payload["baseRows"] = sorted(
        base_rows,
        key=lambda row: (str(row.get("weekStart", "")), normalize_name(row.get("mopName"))),
    )
    return payload["baseRows"]


def recompute_totals(payload: dict[str, Any]) -> None:
    totals = {key: 0 for key in METRIC_ZEROES}
    for row in payload.get("baseRows", []):
        if row.get("aggregatePlan"):
            continue
        for key in totals:
            totals[key] += parse_int(row.get(key))
    totals["airTimePlan"] = format_duration(totals["airTimePlanSeconds"])
    totals["airTimeFact"] = format_duration(totals["airTimeFactSeconds"])
    totals["targetMinutesAfterMeetingFact"] = format_duration(
        totals["targetMinutesAfterMeetingFactSeconds"]
    )
    payload["totals"] = totals


def shared_plan_metadata(store: dict[str, Any]) -> dict[str, Any]:
    months = []
    for month, month_plan in sorted(store.get("months", {}).items()):
        months.append(
            {
                "month": month,
                "fileName": month_plan.get("fileName", ""),
                "publishedAt": month_plan.get("publishedAt", ""),
                "managerCount": parse_int(month_plan.get("managerCount")),
                "hasAggregatePlan": bool(month_plan.get("hasAggregatePlan")),
                "skippedNames": month_plan.get("skippedNames", []),
            }
        )
    return {
        "schemaVersion": STORE_SCHEMA_VERSION,
        "updatedAt": store.get("updatedAt", ""),
        "latestMonth": months[-1]["month"] if months else "",
        "months": months,
    }


def apply_store_to_dashboard(store_path: Path, data_path: Path) -> None:
    if not data_path.exists():
        raise SharedPlanError(f"Файл данных dashboard не найден: {data_path}")
    store = read_store(store_path)
    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SharedPlanError(f"Не удалось прочитать данные dashboard: {exc}") from exc

    shared_rows = build_shared_plan_rows(store)
    rows = merge_shared_plan_rows(payload, shared_rows)
    payload["sharedPlans"] = shared_plan_metadata(store)
    payload["generatedAt"] = datetime.now().isoformat(timespec="seconds")
    update_filters(payload, rows)
    recompute_totals(payload)
    update_overview(payload)
    write_payload(payload, data_path)
    
    # Also update the JavaScript data file
    js_path = data_path.parent / data_path.name.replace('.json', '.js')
    write_js_data(payload, js_path)


def write_js_data(payload: dict[str, Any], js_path: Path) -> None:
    """Write JSON payload as JavaScript variable assignment."""
    try:
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write('window.MOP_REPORT_DASHBOARD_DATA = ')
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write(';\n')
    except (OSError, IOError) as exc:
        raise SharedPlanError(f"Не удалось написать JS файл: {exc}") from exc


def main() -> int:
    try:
        args = parse_args()
        if args.command == "from-xlsx":
            store_path = Path(args.store)
            store = read_store(store_path)
            submission = normalize_submission(workbook_submission(Path(args.xlsx_file)))
            apply_submission(store, submission)
            write_store(store_path, store)
            print(f"Shared plan imported: {submission['month']}")
            print(f"Managers: {submission['managerCount']}")
            print(f"Store: {store_path}")
            return 0

        if args.command == "publish-event":
            store_path = Path(args.store)
            store = read_store(store_path)
            submission = submission_from_issue_event(Path(args.event_file))
            apply_submission(store, submission)
            write_store(store_path, store)
            print(f"Shared plan action: {submission['action']}")
            print(f"Month: {submission['month']}")
            print(f"Store: {store_path}")
            return 0

        if args.command == "apply":
            apply_store_to_dashboard(Path(args.store), Path(args.dashboard_data))
            print(f"Shared plans applied: {args.store}")
            print(f"Dashboard data: {args.dashboard_data}")
            return 0
        raise SharedPlanError("Неизвестная команда.")
    except SharedPlanError as exc:
        print(f"Shared plan error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Unhandled error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
