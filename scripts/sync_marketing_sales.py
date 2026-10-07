from __future__ import annotations

import os
import re
import sys
from calendar import monthrange
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import sync_mop_report as sync


SOURCE_MAP = {
    "leadit": "КЦ",
    "avito": "Авито",
    "selfwalk": "Самоход",
    "recommendation": "Рекомендация",
}
REPORT_CHANNELS = tuple(SOURCE_MAP.values())
UNKNOWN_SOURCE = "Не определено"
MONTHS = {
    "январь": 1,
    "февраль": 2,
    "март": 3,
    "апрель": 4,
    "май": 5,
    "июнь": 6,
    "июль": 7,
    "август": 8,
    "сентябрь": 9,
    "октябрь": 10,
    "ноябрь": 11,
    "декабрь": 12,
}
UNLINKED_CLIENT_DEALS = {
    "Благина Наталья Анатольевна": "5377",
    "Беклемышева Людмила Михайловна": "6147",
    "Тагиров Арсен Седирович": "1656",
}


@dataclass(frozen=True)
class RegistrySale:
    month_key: str
    deal_id: str
    client_name: str
    source_row: int


@dataclass(frozen=True)
class MarketingMeeting:
    month_key: str
    deal_id: str
    meeting_date: date


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ").strip()).lower().replace("ё", "е")


def month_key(value: Any, default_year: int | None = None) -> str:
    text = normalized(value)
    match = re.fullmatch(r"([а-я]+)(?:\s+(\d{4}))?", text)
    if not match:
        return ""
    month = MONTHS.get(match.group(1))
    year = int(match.group(2)) if match.group(2) else default_year
    if not month or not year:
        return ""
    return f"{year:04d}-{month:02d}"


def deal_id_from_link(value: Any) -> str:
    match = re.search(r"/crm/deal/details/(\d+)/?", str(value or ""), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def registry_sales(rows: list[list[Any]], report_year: int) -> list[RegistrySale]:
    sales: list[RegistrySale] = []
    for source_row, row in enumerate(rows, start=2):
        # Source range is B:X: month=B, status=D, client=J, Bitrix link=X.
        month = month_key(row[0] if len(row) > 0 else "")
        status = normalized(row[2] if len(row) > 2 else "")
        if status != "завершена" or not month.startswith(f"{report_year:04d}-"):
            continue
        client_name = re.sub(r"\s+", " ", str(row[8] if len(row) > 8 else "").replace("\xa0", " ").strip())
        deal_id = deal_id_from_link(row[22] if len(row) > 22 else "")
        if not deal_id:
            deal_id = UNLINKED_CLIENT_DEALS.get(client_name, "")
        sales.append(RegistrySale(month, deal_id, client_name, source_row))
    return sales


def classify_source(record: dict[str, Any] | None) -> str:
    record = record or {}
    utm_source = normalized(record.get("UTM_SOURCE"))
    if utm_source in SOURCE_MAP:
        return SOURCE_MAP[utm_source]

    title = normalized(record.get("TITLE"))
    has_avito = "авито" in title or "avito" in title
    has_selfwalk = "самоход" in title or "selfwalk" in title
    if has_avito != has_selfwalk:
        return "Авито" if has_avito else "Самоход"
    return UNKNOWN_SOURCE


def count_sales(
    sales: list[RegistrySale],
    deals_by_id: dict[str, dict[str, Any]],
) -> tuple[Counter[tuple[str, str]], list[RegistrySale]]:
    counts: Counter[tuple[str, str]] = Counter()
    unknown: list[RegistrySale] = []
    for sale in sales:
        source = classify_source(deals_by_id.get(sale.deal_id))
        counts[(sale.month_key, source)] += 1
        if source == UNKNOWN_SOURCE:
            unknown.append(sale)
    return counts, unknown


def target_month_keys(target_rows: list[list[Any]], report_year: int) -> set[str]:
    return {
        parsed
        for row in target_rows
        if (parsed := month_key(row[0] if row else "", report_year))
    }


def successful_meetings(
    entries: list[sync.MeetingLogEntry],
    report_months: set[str],
) -> tuple[list[MarketingMeeting], int]:
    candidates = [
        MarketingMeeting(entry.meeting_date.strftime("%Y-%m"), entry.deal_id, entry.meeting_date)
        for entry in entries
        if entry.successful
        and entry.deal_id
        and entry.meeting_date.strftime("%Y-%m") in report_months
    ]
    by_deal: dict[str, MarketingMeeting] = {}
    for meeting in sorted(candidates, key=lambda item: (item.meeting_date, int(item.deal_id))):
        by_deal.setdefault(meeting.deal_id, meeting)
    return list(by_deal.values()), len(candidates) - len(by_deal)


def report_period(report_months: set[str]) -> tuple[date, date]:
    if not report_months:
        raise RuntimeError("No report months found in Данные")
    first_year, first_month = map(int, min(report_months).split("-"))
    last_year, last_month = map(int, max(report_months).split("-"))
    return (
        date(first_year, first_month, 1),
        date(last_year, last_month, monthrange(last_year, last_month)[1]),
    )


def count_meetings(
    meetings: list[MarketingMeeting],
    deals_by_id: dict[str, dict[str, Any]],
    timezone_name: str,
    period_start: date,
    period_end: date,
) -> tuple[Counter[tuple[str, str]], list[MarketingMeeting]]:
    counts: Counter[tuple[str, str]] = Counter()
    excluded: list[MarketingMeeting] = []
    for meeting in meetings:
        record = deals_by_id.get(meeting.deal_id)
        created = sync.parse_bitrix_date((record or {}).get("DATE_CREATE"), timezone_name)
        if created is None:
            raise RuntimeError(f"Deal {meeting.deal_id} has no DATE_CREATE")
        if created < period_start or created > period_end:
            excluded.append(meeting)
            continue
        counts[(meeting.month_key, classify_source(record))] += 1
    return counts, excluded


def sales_cell_updates(
    target_rows: list[list[Any]],
    counts: Counter[tuple[str, str]],
    report_year: int,
    first_row: int = 4,
) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    for offset, row in enumerate(target_rows):
        month = month_key(row[0] if row else "", report_year)
        channel = str(row[1] if len(row) > 1 else "").strip()
        if not month or channel not in REPORT_CHANNELS:
            continue
        updates.append({
            "range": f"'Данные'!F{first_row + offset}",
            "values": [[counts[(month, channel)]]],
        })
    return updates


def meeting_cell_updates(
    target_rows: list[list[Any]],
    counts: Counter[tuple[str, str]],
    report_year: int,
    first_row: int = 4,
) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    for offset, row in enumerate(target_rows):
        month = month_key(row[0] if row else "", report_year)
        channel = str(row[1] if len(row) > 1 else "").strip()
        if not month or channel not in REPORT_CHANNELS:
            continue
        updates.append({
            "range": f"'Данные'!E{first_row + offset}",
            "values": [[counts[(month, channel)]]],
        })
    return updates


def unknown_cell_updates(
    target_rows: list[list[Any]],
    counts: Counter[tuple[str, str]],
    report_year: int,
    first_row: int = 4,
) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    for offset, row in enumerate(target_rows):
        month = month_key(row[0] if row else "", report_year)
        if not month:
            continue
        updates.append({
            "range": f"'Без меток'!C{first_row + offset}",
            "values": [[counts[(month, UNKNOWN_SOURCE)]]],
        })
    return updates


def unknown_meeting_cell_updates(
    target_rows: list[list[Any]],
    counts: Counter[tuple[str, str]],
    report_year: int,
    first_row: int = 4,
) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    for offset, row in enumerate(target_rows):
        month = month_key(row[0] if row else "", report_year)
        if not month:
            continue
        updates.append({
            "range": f"'Без меток'!B{first_row + offset}",
            "values": [[counts[(month, UNKNOWN_SOURCE)]]],
        })
    return updates


def read_values(service: Any, spreadsheet_id: str, range_name: str) -> list[list[Any]]:
    payload = sync.execute_google_request(
        service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueRenderOption="UNFORMATTED_VALUE",
        )
    )
    values = payload.get("values", [])
    if not isinstance(values, list):
        raise RuntimeError(f"Unexpected Google Sheets response for {range_name}")
    return values


def main() -> None:
    sync.load_environment(None)
    source_sheet_id = required_env("MARKETING_SALES_SOURCE_SHEET_ID")
    target_sheet_id = required_env("MARKETING_SALES_TARGET_SHEET_ID")
    report_year = int(os.getenv("MARKETING_SALES_REPORT_YEAR", "2026"))

    settings = sync.load_settings()
    service = sync.build_sheets_service(settings)
    if service is None:
        raise RuntimeError("Google service account credentials are required")

    source_rows = read_values(service, source_sheet_id, "'Реестр Сделок'!B2:X999")
    sales = registry_sales(source_rows, report_year)
    if not sales:
        raise RuntimeError(f"No completed sales found for {report_year}")

    data_rows = read_values(service, target_sheet_id, "'Данные'!A4:B1000")
    unknown_rows = read_values(service, target_sheet_id, "'Без меток'!A4:A1000")
    report_months = target_month_keys(data_rows, report_year)
    period_start, period_end = report_period(report_months)

    meeting_entries = sync.build_meeting_log_entries(service, settings)
    meetings, duplicate_meetings = successful_meetings(meeting_entries, report_months)
    if not meetings:
        raise RuntimeError(f"No successful meetings found for {report_year}")

    session = sync.build_bitrix_session()
    deal_ids = sorted(
        {sale.deal_id for sale in sales if sale.deal_id} | {meeting.deal_id for meeting in meetings},
        key=int,
    )
    deals_by_id = sync.fetch_deals_by_ids_batch(session, settings, deal_ids)
    missing_deals = sorted(set(deal_ids) - set(deals_by_id), key=int)
    if missing_deals:
        raise RuntimeError(f"Bitrix did not return linked deals: {', '.join(missing_deals)}")

    sales_counts, unknown_sales = count_sales(sales, deals_by_id)
    meeting_counts, excluded_meetings = count_meetings(
        meetings,
        deals_by_id,
        settings.report_timezone,
        period_start,
        period_end,
    )
    updates = sales_cell_updates(data_rows, sales_counts, report_year)
    updates.extend(meeting_cell_updates(data_rows, meeting_counts, report_year))
    updates.extend(unknown_cell_updates(unknown_rows, sales_counts, report_year))
    updates.extend(unknown_meeting_cell_updates(unknown_rows, meeting_counts, report_year))
    if not updates:
        raise RuntimeError("No matching target rows found in Данные or Без меток")

    sync.execute_google_request(
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=target_sheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        )
    )

    print(
        "Marketing metrics synced: "
        f"{len(sales)} completed sales, {len(meetings) - len(excluded_meetings)} unique meetings, "
        f"{duplicate_meetings} duplicate meeting rows removed, {len(updates)} target cells"
    )
    for month in sorted(report_months):
        sales_summary = ", ".join(
            f"{source}={sales_counts[(month, source)]}"
            for source in (*REPORT_CHANNELS, UNKNOWN_SOURCE)
        )
        meeting_summary = ", ".join(
            f"{source}={meeting_counts[(month, source)]}"
            for source in (*REPORT_CHANNELS, UNKNOWN_SOURCE)
        )
        print(f"{month} sales: {sales_summary}")
        print(f"{month} meetings: {meeting_summary}")
    if unknown_sales:
        print("Unclassified registry rows: " + ", ".join(str(sale.source_row) for sale in unknown_sales))
    if excluded_meetings:
        print(
            "Meetings excluded because the deal was created outside the report period: "
            + ", ".join(meeting.deal_id for meeting in excluded_meetings)
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(sync.safe_error_text(exc), file=sys.stderr)
        raise SystemExit(1)
