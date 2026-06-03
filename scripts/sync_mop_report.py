from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time as time_module
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_MEETING_LOG_SHEET_ID = "1CNT1xTe5uBHo4W4ZLUh3qZLmgWy7wxe7nSsCtDXwwIo"
DEFAULT_MEETING_LOG_SHEET_NAME = "Meetings"
DEFAULT_DEAL_APPROVED_MORTGAGE_FIELD = "UF_DEAL_MORTGAGE_APPROVED"
DEFAULT_DEAL_RESERVATION_FIELD = "UF_DEAL_WHERE_PUT_RESERVATION"
SUCCESSFUL_MEETING_STATUSES = {"прошла успешно"}
DEFAULT_INCLUDED_MOPS = (
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
DEFAULT_MOP_NAMES_BY_ID = {
    "39": "Погребинский Артем",
    "159": "Черткова Ирина",
    "160": "Газисова Мария",
    "161": "Попова Олеся",
    "174": "Губайдулина Заррина",
    "189": "Камболин Александр",
    "190": "Тончу Ростислав",
    "194": "Жуков Лев",
    "195": "Попова Юлия",
    "197": "Гавриленко Елена",
}
DEFAULT_ACTIVE_DEAL_CATEGORY_NAMES = ("Льготная ипотека",)
CRM_DEAL_OWNER_TYPE_ID = 2
ACTIVE_DEAL_BASE_FIELDS = [
    "ID",
    "TITLE",
    "ASSIGNED_BY_ID",
    "STAGE_ID",
    "STAGE_SEMANTIC_ID",
    "CATEGORY_ID",
    "DATE_CREATE",
    "DATE_MODIFY",
    "CLOSEDATE",
    "CLOSED",
    "OPPORTUNITY",
    "CURRENCY_ID",
]
ACTIVITY_SELECT_FIELDS = [
    "ID",
    "OWNER_ID",
    "OWNER_TYPE_ID",
    "TYPE_ID",
    "PROVIDER_ID",
    "PROVIDER_TYPE_ID",
    "SUBJECT",
    "START_TIME",
    "END_TIME",
    "CREATED",
    "LAST_UPDATED",
    "COMPLETED",
    "DIRECTION",
]

MOP_REPORT_HEADERS = [
    "Спринт",
    "МОП",
    "Продажи план",
    "Продажи факт",
    "Продажи %",
    "Встречи план",
    "Встречи факт",
    "Встречи %",
    "Брони план",
    "Брони факт",
    "Брони %",
    "Ипотеки план",
    "Ипотеки факт",
    "Ипотеки %",
    "Звонки факт",
    "Эфир план",
    "Эфир факт",
    "Эфир %",
]

PLAN_HEADER_ALIASES = {
    "week": {"неделя", "спринт", "период", "week", "sprint", "period"},
    "week_start": {
        "начало недели",
        "начало спринта",
        "старт недели",
        "старт спринта",
        "от",
        "week start",
        "sprint start",
        "date from",
    },
    "mop_id": {
        "id моп",
        "id менеджера",
        "id ответственного",
        "bitrix id",
        "user id",
        "assigned by id",
    },
    "mop_name": {
        "моп",
        "менеджер",
        "ответственный",
        "сотрудник",
        "фио",
        "sales manager",
        "manager",
    },
    "meeting_plan": {
        "встречи",
        "встречи план",
        "план встреч",
        "план встречи",
        "проведенные встречи план",
        "meetings plan",
    },
    "sale_plan": {
        "продажи",
        "продажи план",
        "план продаж",
        "план по продажам",
        "сделки",
        "сделки план",
        "план сделок",
        "план по сделкам",
        "созданные сделки план",
        "deals plan",
        "sales plan",
    },
    "reservation_plan": {
        "брони",
        "брони план",
        "план броней",
        "план брони",
        "созданные брони план",
        "reservations plan",
    },
    "mortgage_plan": {
        "ипотеки",
        "ипотеки план",
        "план ипотек",
        "план ипотеки",
        "одобренные ипотеки план",
        "mortgages plan",
    },
    "air_time_plan": {
        "эфир",
        "эфир план",
        "план эфира",
        "эфирное время план",
        "целевое эфирное время",
        "target air time",
        "air time plan",
    },
}

MEETING_LOG_HEADER_ALIASES = {
    "status": {"статус", "status", "результат", "result"},
    "meeting_start": {"начало встречи", "start", "meeting start"},
    "responsible": {"ответственный", "моп", "менеджер", "responsible", "manager"},
    "deal_id": {"id сделки", "deal id", "id deal"},
    "deal_link": {"ссылка на сделку", "deal link", "link"},
}


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReportWindow:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Settings:
    bitrix_webhook_url: str
    bitrix_request_timeout: int
    bitrix_approved_mortgage_field: str
    bitrix_reservation_field: str
    bitrix_stage_field: str
    bitrix_success_stage_ids: tuple[str, ...]
    google_service_account_file: str | None
    google_service_account_json: str | None
    google_meeting_log_sheet_id: str
    google_meeting_log_sheet_name: str
    report_timezone: str
    report_period_mode: str
    report_start_date: str


@dataclass(frozen=True)
class MopSettings:
    plan_sheet_id: str
    plan_sheet_name: str
    plan_required: bool
    dashboard_dir: Path
    deal_date_field: str
    approved_mortgage_date_field: str
    reservation_date_field: str
    assigned_field: str
    unknown_mop_name: str
    include_user_labels: tuple[str, ...]
    include_users: frozenset[str]
    exclude_users: frozenset[str]
    call_min_duration_seconds: int
    active_deal_category_names: tuple[str, ...]


@dataclass(frozen=True)
class MeetingLogEntry:
    meeting_date: date
    deal_id: str
    mop_name: str


@dataclass(frozen=True)
class ActiveDealActivity:
    date: date
    kind: str
    completed: bool = True


@dataclass
class MopMetricSet:
    sales: int = 0
    meetings: int = 0
    reservations: int = 0
    approved_mortgages: int = 0
    calls: int = 0
    air_seconds: int = 0

    def add(self, other: "MopMetricSet") -> None:
        self.sales += other.sales
        self.meetings += other.meetings
        self.reservations += other.reservations
        self.approved_mortgages += other.approved_mortgages
        self.calls += other.calls
        self.air_seconds += other.air_seconds

    def as_dict(self, suffix: str) -> dict[str, int]:
        result = {
            f"sales{suffix}": self.sales,
            f"meetings{suffix}": self.meetings,
            f"reservations{suffix}": self.reservations,
            f"approvedMortgages{suffix}": self.approved_mortgages,
            f"airTime{suffix}Seconds": self.air_seconds,
        }
        if suffix == "Fact":
            result["callsFact"] = self.calls
        return result


@dataclass
class MopIdentity:
    mop_id: str = ""
    mop_name: str = ""


@dataclass
class MopReportData:
    facts: dict[date, dict[str, MopMetricSet]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(MopMetricSet))
    )
    plans: dict[date, dict[str, MopMetricSet]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(MopMetricSet))
    )
    identities: dict[str, MopIdentity] = field(default_factory=dict)
    user_ids: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanEntry:
    week_start: date
    mop_id: str
    mop_name: str
    metrics: MopMetricSet


@dataclass(frozen=True)
class BuiltReport:
    rows: list[list[Any]]
    group_ranges: list[tuple[int, int]]
    summary_rows: list[int]
    detail_count: int
    week_count: int
    mop_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build dashboard data for a weekly MOP plan/fact report from Bitrix24 and Google Sheets."
    )
    parser.add_argument("--env-file", help="Path to env file. Defaults to bitrix.env or .env.")
    parser.add_argument("--dry-run", action="store_true", help="Kept for compatibility; the script never writes a report sheet.")
    return parser.parse_args()


def load_environment(env_file: str | None) -> None:
    if env_file:
        env_path = Path(env_file)
        if not env_path.exists():
            raise ConfigError(f"Env file not found: {env_path}")
        load_dotenv(env_path, override=True)
        return

    for candidate in ("bitrix.env", ".env"):
        candidate_path = Path(candidate)
        if candidate_path.exists():
            load_dotenv(candidate_path, override=False)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigError(f"Missing required env var: {name}")
    return value.strip()


def read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "да"}:
        return True
    if normalized in {"0", "false", "no", "n", "нет"}:
        return False
    raise ConfigError(f"Invalid boolean value for {name}: {raw}")


def read_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid integer value for {name}: {raw}") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero.")
    return value


def read_non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid integer value for {name}: {raw}") from exc
    if value < 0:
        raise ConfigError(f"{name} must be greater than or equal to zero.")
    return value


def read_filter_tokens(name: str, default_values: tuple[str, ...] = ()) -> frozenset[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return frozenset(normalize_key(item) for item in default_values if item.strip())
    return frozenset(normalize_key(item) for item in raw.split(",") if item.strip())


def read_filter_labels(name: str, default_values: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return tuple(item.strip() for item in default_values if item.strip())
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def load_settings() -> Settings:
    google_service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip() or None
    google_service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip() or None
    raw_success_stages = os.getenv("BITRIX_SUCCESS_STAGE_IDS", "").strip() or "WON,CLOSED"
    bitrix_success_stage_ids = tuple(
        normalize_key(stage) for stage in raw_success_stages.split(",") if stage.strip()
    )

    if not google_service_account_file:
        credentials_dir = Path.cwd() / "Credentials"
        discovered_files = sorted(credentials_dir.glob("*.json"))
        if len(discovered_files) == 1:
            google_service_account_file = str(discovered_files[0])

    return Settings(
        bitrix_webhook_url=require_env("BITRIX_WEBHOOK_URL"),
        bitrix_request_timeout=read_positive_int_env("BITRIX_REQUEST_TIMEOUT", 120),
        bitrix_approved_mortgage_field=(
            os.getenv("BITRIX_APPROVED_MORTGAGE_FIELD", DEFAULT_DEAL_APPROVED_MORTGAGE_FIELD).strip()
            or DEFAULT_DEAL_APPROVED_MORTGAGE_FIELD
        ),
        bitrix_reservation_field=(
            os.getenv("BITRIX_RESERVATION_FIELD", DEFAULT_DEAL_RESERVATION_FIELD).strip()
            or DEFAULT_DEAL_RESERVATION_FIELD
        ),
        bitrix_stage_field=os.getenv("BITRIX_STAGE_FIELD", "STAGE_ID").strip() or "STAGE_ID",
        bitrix_success_stage_ids=bitrix_success_stage_ids,
        google_service_account_file=google_service_account_file,
        google_service_account_json=google_service_account_json,
        google_meeting_log_sheet_id=(
            os.getenv("GOOGLE_MEETING_LOG_SHEET_ID", DEFAULT_MEETING_LOG_SHEET_ID).strip()
            or DEFAULT_MEETING_LOG_SHEET_ID
        ),
        google_meeting_log_sheet_name=(
            os.getenv("GOOGLE_MEETING_LOG_SHEET_NAME", DEFAULT_MEETING_LOG_SHEET_NAME).strip()
            or DEFAULT_MEETING_LOG_SHEET_NAME
        ),
        report_timezone=os.getenv("REPORT_TIMEZONE", "Asia/Yekaterinburg").strip() or "Asia/Yekaterinburg",
        report_period_mode=os.getenv("REPORT_PERIOD_MODE", "from_start_date").strip().lower()
        or "from_start_date",
        report_start_date=os.getenv("REPORT_START_DATE", "2026-03-01").strip() or "2026-03-01",
    )


def load_mop_settings(settings: Settings) -> MopSettings:
    plan_sheet_id = os.getenv("MOP_PLAN_SHEET_ID", "").strip() or os.getenv("GOOGLE_SHEET_ID", "").strip()
    deal_date_field = os.getenv("MOP_DEAL_DATE_FIELD", "DATE_CREATE").strip() or "DATE_CREATE"

    return MopSettings(
        plan_sheet_id=plan_sheet_id,
        plan_sheet_name=os.getenv("MOP_PLAN_SHEET_NAME", "Планы МОП").strip() or "Планы МОП",
        plan_required=read_bool_env("MOP_PLAN_REQUIRED", False),
        dashboard_dir=Path(os.getenv("MOP_DASHBOARD_DIR", "dashboard").strip() or "dashboard"),
        deal_date_field=deal_date_field,
        approved_mortgage_date_field=(
            os.getenv("MOP_APPROVED_MORTGAGE_DATE_FIELD", "").strip() or deal_date_field
        ),
        reservation_date_field=os.getenv("MOP_RESERVATION_DATE_FIELD", "").strip() or deal_date_field,
        assigned_field=os.getenv("MOP_ASSIGNED_FIELD", "ASSIGNED_BY_ID").strip() or "ASSIGNED_BY_ID",
        unknown_mop_name=os.getenv("MOP_UNKNOWN_USER", "Без ответственного").strip()
        or "Без ответственного",
        include_user_labels=read_filter_labels("MOP_INCLUDE_USERS", DEFAULT_INCLUDED_MOPS),
        include_users=read_filter_tokens("MOP_INCLUDE_USERS", DEFAULT_INCLUDED_MOPS),
        exclude_users=read_filter_tokens("MOP_EXCLUDE_USERS"),
        call_min_duration_seconds=read_non_negative_int_env("MOP_CALL_MIN_DURATION_SECONDS", 0),
        active_deal_category_names=read_filter_labels(
            "MOP_ACTIVE_DEAL_CATEGORY_NAMES",
            DEFAULT_ACTIVE_DEAL_CATEGORY_NAMES,
        ),
    )


def resolve_report_window(settings: Settings) -> ReportWindow:
    tz = ZoneInfo(settings.report_timezone)
    now = datetime.now(tz)
    start_date = datetime.strptime(settings.report_start_date, "%Y-%m-%d").date()
    start = datetime.combine(start_date, time.min, tzinfo=tz)
    end = now

    if settings.report_period_mode not in {"from_start_date", "current_month", "previous_month", "all_time"}:
        raise ConfigError(
            "Unsupported REPORT_PERIOD_MODE. Use from_start_date, current_month, previous_month, or all_time."
        )
    if settings.report_period_mode == "current_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif settings.report_period_mode == "previous_month":
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = current_month_start - timedelta(seconds=1)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif settings.report_period_mode == "all_time":
        start = datetime(2000, 1, 1, tzinfo=tz)

    if start > end:
        raise ConfigError("Resolved report window is invalid.")
    return ReportWindow(start, end)


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я_ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def safe_error_text(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        reason = exc.response.reason or "HTTP error"
        return f"{status} {reason}"
    text = str(exc)
    text = re.sub(r"https?://\S+", "<redacted-url>", text)
    return text


def parse_sheet_datetime(value: Any, timezone_name: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None

    tz = ZoneInfo(timezone_name)
    normalized = text.replace("T", " ").replace("/", "-")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None

    if parsed is None:
        for pattern in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%Y-%m-%d",
            "%d.%m.%Y",
        ):
            try:
                parsed = datetime.strptime(normalized, pattern)
                break
            except ValueError:
                continue

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def parse_bitrix_datetime(value: Any, timezone_name: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None

    tz = ZoneInfo(timezone_name)
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = parse_sheet_datetime(text, timezone_name)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def build_google_credentials(settings: Settings):
    from google.oauth2.service_account import Credentials

    if settings.google_service_account_file:
        credential_path = Path(settings.google_service_account_file)
        if not credential_path.is_absolute():
            credential_path = Path.cwd() / credential_path
        if not credential_path.exists():
            raise ConfigError(f"Google service account file not found: {credential_path}")
        return Credentials.from_service_account_file(str(credential_path), scopes=GOOGLE_SCOPES)

    assert settings.google_service_account_json is not None
    try:
        info = json.loads(settings.google_service_account_json)
    except json.JSONDecodeError as exc:
        raise ConfigError("GOOGLE_SERVICE_ACCOUNT_JSON must contain valid JSON.") from exc
    return Credentials.from_service_account_info(info, scopes=GOOGLE_SCOPES)


def build_sheets_service(settings: Settings):
    from googleapiclient.discovery import build

    if not settings.google_service_account_file and not settings.google_service_account_json:
        return None
    credentials = build_google_credentials(settings)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def execute_google_request(request: Any) -> dict[str, Any]:
    from googleapiclient.errors import HttpError

    transient_statuses = {429, 500, 502, 503, 504}
    for attempt in range(1, 5):
        try:
            return request.execute(num_retries=2)
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status not in transient_statuses or attempt == 4:
                raise
            time_module.sleep(min(2 ** attempt, 10))
    return {}


def quote_sheet_title(sheet_title: str) -> str:
    escaped_title = sheet_title.replace("'", "''")
    return sheet_title if re.fullmatch(r"[A-Za-z0-9_]+", sheet_title) else f"'{escaped_title}'"


def resolve_sheet_title(service: Any, spreadsheet_id: str, requested_title: str) -> str:
    metadata = execute_google_request(
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="properties(title),sheets(properties(title))")
    )
    sheets = metadata.get("sheets", [])
    if not sheets:
        raise ConfigError("The target spreadsheet has no sheets.")

    spreadsheet_title = metadata["properties"]["title"]
    selected_sheet = next((sheet for sheet in sheets if sheet["properties"]["title"] == requested_title), None)
    if selected_sheet is None and requested_title == spreadsheet_title and len(sheets) == 1:
        selected_sheet = sheets[0]
    elif selected_sheet is None and len(sheets) == 1:
        selected_sheet = sheets[0]
    if selected_sheet is None:
        available = ", ".join(sheet["properties"]["title"] for sheet in sheets)
        raise ConfigError(f"Sheet '{requested_title}' not found. Available sheets: {available}")
    return selected_sheet["properties"]["title"]


def normalize_webhook_base(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path or "/"
    if path.endswith(".json"):
        path = path.rsplit("/", 1)[0] + "/"
    elif not path.endswith("/"):
        path += "/"
    return urlunparse(parsed._replace(path=path, params="", query="", fragment=""))


def build_bitrix_method_url(base_url: str, method_name: str) -> str:
    return f"{normalize_webhook_base(base_url)}{method_name}.json"


def build_bitrix_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    return session


def execute_bitrix_method(
    session: requests.Session,
    settings: Settings,
    method_name: str,
    params: list[tuple[str, Any]] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = session.get(
        build_bitrix_method_url(settings.bitrix_webhook_url, method_name),
        params=params or {},
        timeout=settings.bitrix_request_timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Bitrix API error: {payload['error']} - {payload.get('error_description', '')}")
    return payload


def execute_bitrix_post_method(
    session: requests.Session,
    settings: Settings,
    method_name: str,
    params: list[tuple[str, Any]] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = session.post(
        build_bitrix_method_url(settings.bitrix_webhook_url, method_name),
        data=params or {},
        timeout=settings.bitrix_request_timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Bitrix API error: {payload['error']} - {payload.get('error_description', '')}")
    return payload


def execute_bitrix_deal_get(session: requests.Session, settings: Settings, deal_id: str) -> dict[str, Any]:
    payload = execute_bitrix_method(session, settings, "crm.deal.get", {"id": deal_id})
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected Bitrix API response: crm.deal.get result is not an object.")
    return result


def fetch_day_deals(
    session: requests.Session,
    settings: Settings,
    date_field: str,
    day_start: datetime,
    day_end: datetime,
    select_fields: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    next_page: int | None = 0
    while next_page is not None:
        params: list[tuple[str, Any]] = [
            ("start", next_page),
            (f"filter[>={date_field}]", day_start.isoformat(timespec="seconds")),
            (f"filter[<={date_field}]", day_end.isoformat(timespec="seconds")),
        ]
        for field_name in select_fields:
            params.append(("select[]", field_name))

        payload = execute_bitrix_method(session, settings, "crm.deal.list", params)
        result = payload.get("result", [])
        if not isinstance(result, list):
            raise RuntimeError("Unexpected Bitrix API response: crm.deal.list result is not a list.")
        records.extend(result)
        raw_next = payload.get("next")
        next_page = int(raw_next) if raw_next is not None else None
    return records


def fetch_deal_list(
    session: requests.Session,
    settings: Settings,
    filters: dict[str, Any],
    select_fields: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    next_page: int | None = 0
    while next_page is not None:
        params: list[tuple[str, Any]] = [("start", next_page)]
        for field_name, field_value in filters.items():
            params.append((f"filter[{field_name}]", field_value))
        for field_name in select_fields:
            params.append(("select[]", field_name))

        payload = execute_bitrix_method(session, settings, "crm.deal.list", params)
        result = payload.get("result", [])
        if not isinstance(result, list):
            raise RuntimeError("Unexpected Bitrix API response: crm.deal.list result is not a list.")
        records.extend(result)
        raw_next = payload.get("next")
        next_page = int(raw_next) if raw_next is not None else None
    return records


def fetch_paged_method(
    session: requests.Session,
    settings: Settings,
    method_name: str,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    next_page: int | None = 0
    while next_page is not None:
        params: list[tuple[str, Any]] = [("start", next_page)]
        for field_name, field_value in filters.items():
            params.append((f"FILTER[{field_name}]", field_value))
        payload = execute_bitrix_method(session, settings, method_name, params)
        result = payload.get("result", [])
        if not isinstance(result, list):
            raise RuntimeError(f"Unexpected Bitrix API response for {method_name}: result is not a list.")
        records.extend(result)
        raw_next = payload.get("next")
        next_page = int(raw_next) if raw_next is not None else None
    return records


def parse_numeric_id(value: Any) -> str:
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else ""


def extract_deal_id_from_link(value: Any) -> str:
    match = re.search(r"/crm/deal/details/(\d+)/?", str(value or ""), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def find_matching_column(rows: list[list[Any]], aliases: set[str]) -> tuple[int, int] | None:
    for row_index, row in enumerate(rows):
        for column_index, cell in enumerate(row):
            if normalize_text(cell) in aliases:
                return row_index, column_index
    return None


def find_meeting_log_columns(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    column_map: dict[str, int] = {}
    matched_rows: list[int] = []
    for canonical_name in ("status", "meeting_start"):
        match = find_matching_column(rows, MEETING_LOG_HEADER_ALIASES[canonical_name])
        if match is None:
            raise ConfigError("Could not find required meeting log columns: status and meeting start.")
        row_index, column_index = match
        column_map[canonical_name] = column_index
        matched_rows.append(row_index)

    for canonical_name in ("responsible", "deal_id", "deal_link"):
        match = find_matching_column(rows, MEETING_LOG_HEADER_ALIASES[canonical_name])
        if match is not None:
            row_index, column_index = match
            column_map[canonical_name] = column_index
            matched_rows.append(row_index)

    if "deal_id" not in column_map and "deal_link" not in column_map:
        raise ConfigError("Could not find 'ID сделки' or 'Ссылка на сделку' columns in the meeting log sheet.")
    return max(matched_rows), column_map


def build_successful_meeting_entries(service: Any, settings: Settings) -> list[MeetingLogEntry]:
    sheet_title = resolve_sheet_title(
        service,
        settings.google_meeting_log_sheet_id,
        settings.google_meeting_log_sheet_name,
    )
    values = execute_google_request(
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=settings.google_meeting_log_sheet_id,
            range=f"{quote_sheet_title(sheet_title)}!A:Z",
            majorDimension="ROWS",
        )
    ).get("values", [])
    if not values:
        return []

    header_row_index, column_map = find_meeting_log_columns(values)
    entries: list[MeetingLogEntry] = []
    for row in values[header_row_index + 1 :]:
        status_index = column_map["status"]
        status_value = row[status_index] if status_index < len(row) else ""
        if normalize_text(status_value) not in SUCCESSFUL_MEETING_STATUSES:
            continue

        start_index = column_map["meeting_start"]
        meeting_datetime = parse_sheet_datetime(
            row[start_index] if start_index < len(row) else "",
            settings.report_timezone,
        )
        if meeting_datetime is None:
            continue

        deal_id = ""
        deal_id_index = column_map.get("deal_id")
        if deal_id_index is not None and deal_id_index < len(row):
            deal_id = parse_numeric_id(row[deal_id_index])
        if not deal_id:
            deal_link_index = column_map.get("deal_link")
            if deal_link_index is not None and deal_link_index < len(row):
                deal_id = extract_deal_id_from_link(row[deal_link_index])
        responsible_index = column_map.get("responsible")
        mop_name = ""
        if responsible_index is not None and responsible_index < len(row):
            mop_name = str(row[responsible_index] or "").strip()
        if deal_id or mop_name:
            entries.append(MeetingLogEntry(meeting_datetime.date(), deal_id, mop_name))
    return entries


def iterate_report_dates(window: ReportWindow) -> list[date]:
    days: list[date] = []
    current = window.start.date()
    while current <= window.end.date():
        days.append(current)
        current += timedelta(days=1)
    return days


def day_bounds(current_date: date, window: ReportWindow) -> tuple[datetime, datetime]:
    day_start = datetime.combine(current_date, time.min, tzinfo=window.start.tzinfo)
    day_end = datetime.combine(current_date, time.max, tzinfo=window.start.tzinfo)
    if current_date == window.end.date():
        day_end = window.end
    return day_start, day_end


def month_end_for_date(current_date: date) -> date:
    if current_date.month == 12:
        return date(current_date.year, 12, 31)
    return date(current_date.year, current_date.month + 1, 1) - timedelta(days=1)


def week_start_for_date(current_date: date) -> date:
    sprint_day = min(22, 1 + ((current_date.day - 1) // 7) * 7)
    return date(current_date.year, current_date.month, sprint_day)


def week_end_for_start(week_start: date) -> date:
    if week_start.day >= 22:
        return month_end_for_date(week_start)
    return week_start + timedelta(days=6)


def format_short_date(current_date: date) -> str:
    return current_date.strftime("%d.%m")


def format_sheet_date(current_date: date) -> str:
    return current_date.strftime("%d.%m.%Y")


def format_week_label(week_start: date) -> str:
    return f"{format_short_date(week_start)}-{format_sheet_date(week_end_for_start(week_start))}"


def parse_week_start(value: Any, window: ReportWindow, timezone_name: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    iso_week_match = re.search(r"(\d{4})\s*[- ]?w(?:eek)?\s*(\d{1,2})", text, flags=re.IGNORECASE)
    if iso_week_match:
        year, week = (int(part) for part in iso_week_match.groups())
        return week_start_for_date(date.fromisocalendar(year, week, 1))

    parsed = parse_sheet_datetime(text, timezone_name)
    if parsed is not None:
        return week_start_for_date(parsed.date())

    date_match = re.search(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?", text)
    if not date_match:
        return None
    day, month, raw_year = date_match.groups()
    year = window.start.year
    if raw_year:
        year = int(raw_year)
        if year < 100:
            year += 2000
    try:
        return week_start_for_date(date(year, int(month), int(day)))
    except ValueError:
        return None


def parse_number(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    normalized = text.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if not match:
        return 0
    return int(round(float(match.group(0))))


def parse_duration_seconds(value: Any) -> int:
    text = str(value or "").strip().lower()
    if not text:
        return 0
    time_match = re.fullmatch(r"(\d{1,5}):(\d{2})(?::(\d{2}))?", text)
    if time_match:
        first, second, third = time_match.groups()
        if third is not None:
            return int(first) * 3600 + int(second) * 60 + int(third)
        return int(first) * 60 + int(second)

    total = 0.0
    for multiplier, pattern in (
        (3600, r"(\d+(?:[,.]\d+)?)\s*(?:ч|час|часа|hours?|h)\b"),
        (60, r"(\d+(?:[,.]\d+)?)\s*(?:м|мин|минут|minutes?|m)\b"),
        (1, r"(\d+(?:[,.]\d+)?)\s*(?:с|сек|секунд|seconds?|s)\b"),
    ):
        match = re.search(pattern, text)
        if match:
            total += float(match.group(1).replace(",", ".")) * multiplier
    if total:
        return int(round(total))
    return parse_number(text) * 60


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def completion_cell(plan: int, fact: int) -> str:
    if plan <= 0:
        return "—" if fact > 0 else ""
    return f"{fact / plan:.0%}"


def resolve_boolean_field(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "да", "on", "ok", "checked", "t"}


def resolve_non_empty_field(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def resolve_deal_closed(record: dict[str, Any], settings: Settings) -> bool:
    if normalize_key(record.get("STAGE_SEMANTIC_ID")) == "s":
        return True
    stage_value = record.get(settings.bitrix_stage_field)
    if stage_value is None:
        return False
    return normalize_key(stage_value) in settings.bitrix_success_stage_ids


def normalize_mop_token(mop_id: str, mop_name: str) -> set[str]:
    tokens = set()
    if mop_id:
        tokens.add(normalize_key(mop_id))
        tokens.add(f"id:{normalize_key(mop_id)}")
    if mop_name:
        tokens.add(normalize_key(mop_name))
    return tokens


def mop_filter_matches(filter_value: str, mop_id: str, mop_name: str) -> bool:
    normalized_filter = normalize_key(filter_value)
    if not normalized_filter:
        return False

    tokens = normalize_mop_token(mop_id, mop_name)
    if normalized_filter in tokens:
        return True

    normalized_name = normalize_key(mop_name)
    if not normalized_name:
        return False
    return normalized_filter in normalized_name


def mop_is_allowed(mop_id: str, mop_name: str, settings: MopSettings) -> bool:
    if settings.include_users and not any(
        mop_filter_matches(filter_value, mop_id, mop_name)
        for filter_value in settings.include_users
    ):
        return False
    if settings.exclude_users and any(
        mop_filter_matches(filter_value, mop_id, mop_name)
        for filter_value in settings.exclude_users
    ):
        return False
    return True


def canonical_mop_label(mop_name: str, settings: MopSettings) -> str:
    normalized = normalize_key(mop_name)
    if not normalized:
        return ""

    normalized_parts = sorted(part for part in normalized.split() if part)
    partial_matches: list[str] = []
    for label in settings.include_user_labels:
        normalized_label = normalize_key(label)
        if not normalized_label:
            continue
        if normalized == normalized_label:
            return label
        label_parts = sorted(part for part in normalized_label.split() if part)
        if normalized_parts and normalized_parts == label_parts:
            return label
        if normalized_parts and (
            set(normalized_parts).issubset(set(label_parts))
            or set(label_parts).issubset(set(normalized_parts))
        ):
            partial_matches.append(label)
    if len(partial_matches) == 1:
        return partial_matches[0]
    return mop_name.strip()


def unique_fields(fields: list[str]) -> list[str]:
    result: list[str] = []
    for field_name in fields:
        if field_name and field_name not in result:
            result.append(field_name)
    return result


def parse_bitrix_date(value: Any, timezone_name: str) -> date | None:
    parsed = parse_bitrix_datetime(value, timezone_name)
    return parsed.date() if parsed else None


def date_iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def bitrix_deal_url(settings: Settings, deal_id: str) -> str:
    parsed = urlparse(normalize_webhook_base(settings.bitrix_webhook_url))
    return urlunparse(parsed._replace(path=f"/crm/deal/details/{deal_id}/", params="", query="", fragment=""))


def fetch_deal_stage_names(session: requests.Session, settings: Settings) -> dict[str, str]:
    try:
        payload = execute_bitrix_method(session, settings, "crm.status.list")
    except Exception:
        return {}
    result = payload.get("result", [])
    if not isinstance(result, list):
        return {}
    return {
        str(item.get("STATUS_ID") or ""): str(item.get("NAME") or "").strip()
        for item in result
        if "DEAL_STAGE" in str(item.get("ENTITY_ID") or "") and item.get("STATUS_ID")
    }


def fetch_deal_category_names(session: requests.Session, settings: Settings) -> dict[str, str]:
    try:
        payload = execute_bitrix_method(session, settings, "crm.dealcategory.list")
    except Exception:
        return {}
    result = payload.get("result", [])
    if not isinstance(result, list):
        return {}
    return {
        str(item.get("ID") or ""): str(item.get("NAME") or "").strip()
        for item in result
        if item.get("ID") is not None
    }


def active_deal_category_ids(category_names: dict[str, str], mop_settings: MopSettings) -> set[str]:
    allowed_names = {normalize_key(name) for name in mop_settings.active_deal_category_names if normalize_key(name)}
    if not allowed_names:
        return set()
    return {
        category_id
        for category_id, category_name in category_names.items()
        if normalize_key(category_name) in allowed_names
    }


def classify_activity(record: dict[str, Any]) -> str:
    type_id = str(record.get("TYPE_ID") or "").strip()
    provider_id = normalize_key(record.get("PROVIDER_ID"))
    provider_type = normalize_key(record.get("PROVIDER_TYPE_ID"))
    subject = normalize_key(record.get("SUBJECT"))
    haystack = " ".join((provider_id, provider_type, subject))

    if any(marker in haystack for marker in ("подбор", "selection", "презентац")):
        return "selections"
    if type_id == "2" or "call" in provider_id or "call" in provider_type:
        return "calls"
    if type_id == "1" or "meeting" in provider_id or "meeting" in provider_type or "встреч" in subject:
        return "meetings"
    if type_id == "4" or "email" in provider_id or "mail" in provider_id:
        return "emails"
    if type_id in {"3", "6"} or any(marker in provider_id for marker in ("task", "todo")):
        return "tasks"
    return "other"


def activity_date(record: dict[str, Any], timezone_name: str) -> date | None:
    for field_name in ("START_TIME", "CREATED", "END_TIME", "LAST_UPDATED"):
        current_date = parse_bitrix_date(record.get(field_name), timezone_name)
        if current_date:
            return current_date
    return None


def bitrix_command(method_name: str, params: list[tuple[str, Any]]) -> str:
    return f"{method_name}?{urlencode(params, doseq=True)}"


def execute_bitrix_batch(
    session: requests.Session,
    settings: Settings,
    commands: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not commands:
        return {}, {}, {}
    params: list[tuple[str, Any]] = [("halt", 0)]
    for key, command in commands.items():
        params.append((f"cmd[{key}]", command))
    payload = execute_bitrix_post_method(session, settings, "batch", params)
    result = payload.get("result", {})
    if not isinstance(result, dict):
        return {}, {}, {}
    return (
        result.get("result", {}) if isinstance(result.get("result"), dict) else {},
        result.get("result_next", {}) if isinstance(result.get("result_next"), dict) else {},
        result.get("result_error", {}) if isinstance(result.get("result_error"), dict) else {},
    )


def fetch_deal_activity_events_batch(
    session: requests.Session,
    settings: Settings,
    deal_ids: list[str],
    window: ReportWindow,
) -> dict[str, list[ActiveDealActivity]]:
    events_by_deal: dict[str, list[ActiveDealActivity]] = {deal_id: [] for deal_id in deal_ids}
    pending: list[tuple[str, int]] = [(deal_id, 0) for deal_id in deal_ids]
    while pending:
        batch_items = pending[:50]
        pending = pending[50:]
        commands: dict[str, str] = {}
        key_to_deal: dict[str, str] = {}
        for index, (deal_id, start) in enumerate(batch_items):
            key = f"a{index}"
            key_to_deal[key] = deal_id
            params: list[tuple[str, Any]] = [
                ("start", start),
                ("filter[OWNER_TYPE_ID]", CRM_DEAL_OWNER_TYPE_ID),
                ("filter[OWNER_ID]", deal_id),
            ]
            for field_name in ACTIVITY_SELECT_FIELDS:
                params.append(("select[]", field_name))
            commands[key] = bitrix_command("crm.activity.list", params)

        result, result_next, result_error = execute_bitrix_batch(session, settings, commands)
        if result_error:
            failed = ", ".join(str(key_to_deal.get(key, key)) for key in result_error)
            raise RuntimeError(f"crm.activity.list batch failed for deals: {failed}")

        for key, records in result.items():
            deal_id = key_to_deal.get(key)
            if not deal_id or not isinstance(records, list):
                continue
            for record in records:
                current_date = activity_date(record, settings.report_timezone)
                if current_date is None or current_date > window.end.date():
                    continue
                events_by_deal.setdefault(deal_id, []).append(
                    ActiveDealActivity(
                        date=current_date,
                        kind=classify_activity(record),
                        completed=str(record.get("COMPLETED") or "").upper() == "Y",
                    )
                )
            if key in result_next:
                pending.append((deal_id, int(result_next[key])))

    for events in events_by_deal.values():
        events.sort(key=lambda event: event.date)
    return events_by_deal


def key_for_mop_id(mop_id: str) -> str:
    return f"id:{normalize_key(mop_id)}"


def key_for_mop_name(mop_name: str) -> str:
    normalized = normalize_key(mop_name)
    return f"name:{normalized}" if normalized else "name:unknown"


def remember_identity(data: MopReportData, key: str, mop_id: str, mop_name: str) -> None:
    identity = data.identities.setdefault(key, MopIdentity())
    if mop_id and not identity.mop_id:
        identity.mop_id = mop_id
    if mop_name and not identity.mop_name:
        identity.mop_name = mop_name


def add_fact(
    data: MopReportData,
    event_date: date,
    mop_id: str,
    metric_name: str,
    value: int,
    mop_name: str = "",
) -> None:
    if not mop_id and not mop_name:
        mop_name = "Без ответственного"
    key = key_for_mop_id(mop_id) if mop_id else key_for_mop_name(mop_name)
    if mop_id:
        data.user_ids.add(mop_id)
    remember_identity(data, key, mop_id, mop_name)
    metrics = data.facts[week_start_for_date(event_date)][key]
    setattr(metrics, metric_name, value + getattr(metrics, metric_name))


def add_plan(data: MopReportData, week_start: date, key: str, mop_id: str, mop_name: str, metrics: MopMetricSet) -> None:
    remember_identity(data, key, mop_id, mop_name)
    data.plans[week_start][key].add(metrics)


def fetch_bitrix_user_names(session: requests.Session, settings: Settings, user_ids: set[str]) -> dict[str, str]:
    user_names: dict[str, str] = {}
    for user_id in sorted(user_ids, key=lambda item: int(item) if item.isdigit() else item):
        result: list[dict[str, Any]] = []
        for params in ({"ID": user_id}, {"FILTER[ID]": user_id}):
            try:
                payload = execute_bitrix_method(session, settings, "user.get", params)
            except Exception:
                continue
            raw_result = payload.get("result", [])
            if isinstance(raw_result, list) and raw_result:
                result = raw_result
                break
        if not result:
            user_names[user_id] = DEFAULT_MOP_NAMES_BY_ID.get(user_id, f"Пользователь {user_id}")
            continue

        user = result[0]
        name_parts = [
            str(user.get("LAST_NAME") or "").strip(),
            str(user.get("NAME") or "").strip(),
            str(user.get("SECOND_NAME") or "").strip(),
        ]
        full_name = " ".join(part for part in name_parts if part)
        user_names[user_id] = (
            DEFAULT_MOP_NAMES_BY_ID.get(user_id)
            or full_name
            or str(user.get("LOGIN") or user.get("EMAIL") or f"Пользователь {user_id}")
        )
    return user_names


def hydrate_fact_identities(data: MopReportData, user_names: dict[str, str]) -> None:
    for identity in data.identities.values():
        if identity.mop_id:
            identity.mop_name = (
                DEFAULT_MOP_NAMES_BY_ID.get(identity.mop_id)
                or user_names.get(identity.mop_id)
                or identity.mop_name
                or f"Пользователь {identity.mop_id}"
            )
        elif not identity.mop_name:
            identity.mop_name = "Без ответственного"


def extract_assigned_user_id(record: dict[str, Any], mop_settings: MopSettings) -> str:
    value = record.get(mop_settings.assigned_field)
    if value in (None, "") and mop_settings.assigned_field != "ASSIGNED_BY_ID":
        value = record.get("ASSIGNED_BY_ID")
    if isinstance(value, dict):
        value = value.get("ID") or value.get("id")
    return str(value or "").strip()


def build_deal_metric_facts(
    data: MopReportData,
    session: requests.Session,
    settings: Settings,
    mop_settings: MopSettings,
    window: ReportWindow,
) -> None:
    deal_date_field = mop_settings.deal_date_field or "DATE_CREATE"
    deal_select_fields = unique_fields(
        [
            "ID",
            "ASSIGNED_BY_ID",
            mop_settings.assigned_field,
            deal_date_field,
            "DATE_CREATE",
            "CATEGORY_ID",
            "STAGE_ID",
            "STAGE_SEMANTIC_ID",
            settings.bitrix_stage_field,
        ]
    )
    category_names = fetch_deal_category_names(session, settings)
    category_ids = active_deal_category_ids(category_names, mop_settings)
    deal_records_by_id: dict[str, tuple[dict[str, Any], date]] = {}
    missing_deal_id_index = 0

    if mop_settings.active_deal_category_names and not category_ids:
        data.warnings.append(
            "Продажи: не найдена воронка "
            + ", ".join(mop_settings.active_deal_category_names)
            + "; продажи посчитаны по всем воронкам."
        )

    for current_date in iterate_report_dates(window):
        day_start, day_end = day_bounds(current_date, window)
        base_filters: dict[str, Any] = {
            f">={deal_date_field}": day_start.isoformat(timespec="seconds"),
            f"<={deal_date_field}": day_end.isoformat(timespec="seconds"),
        }
        try:
            if category_ids:
                records: list[dict[str, Any]] = []
                for category_id in sorted(category_ids, key=lambda item: int(item) if item.isdigit() else item):
                    records.extend(
                        fetch_deal_list(
                            session,
                            settings,
                            {**base_filters, "CATEGORY_ID": category_id},
                            deal_select_fields,
                        )
                    )
            else:
                records = fetch_deal_list(session, settings, base_filters, deal_select_fields)
        except Exception as exc:
            data.warnings.append(
                f"Продажи: не удалось загрузить сделки за {current_date.isoformat()}: {safe_error_text(exc)}"
            )
            continue

        for record in records:
            deal_id = str(record.get("ID") or "").strip()
            if deal_id:
                deal_records_by_id.setdefault(deal_id, (record, current_date))
            else:
                missing_deal_id_index += 1
                deal_records_by_id[f"__missing_deal_id__{missing_deal_id_index}"] = (record, current_date)

    for record, current_date in deal_records_by_id.values():
        if not resolve_deal_closed(record, settings):
            continue
        event_datetime = parse_bitrix_datetime(record.get(deal_date_field), settings.report_timezone)
        if event_datetime is None and deal_date_field != "DATE_CREATE":
            event_datetime = parse_bitrix_datetime(record.get("DATE_CREATE"), settings.report_timezone)
        event_date = event_datetime.date() if event_datetime else current_date
        if event_date < window.start.date() or event_date > window.end.date():
            continue
        add_fact(data, event_date, extract_assigned_user_id(record, mop_settings), "sales", 1)

    metric_specs = [
        (
            "approved_mortgages",
            "Ипотеки",
            settings.bitrix_approved_mortgage_field,
            mop_settings.approved_mortgage_date_field,
            [],
            resolve_boolean_field,
        ),
        (
            "reservations",
            "Брони",
            settings.bitrix_reservation_field,
            mop_settings.reservation_date_field,
            ["DATE_CREATE"],
            resolve_non_empty_field,
        ),
    ]
    for metric_name, metric_label, metric_field, date_field, fallback_date_fields, resolver in metric_specs:
        if not metric_field:
            continue
        select_fields = unique_fields(["ID", "ASSIGNED_BY_ID", date_field, *fallback_date_fields, metric_field])
        if mop_settings.assigned_field not in select_fields:
            select_fields.append(mop_settings.assigned_field)

        if metric_name == "reservations":
            filter_date_fields = ["DATE_CREATE"]
        else:
            filter_date_fields = unique_fields([date_field, *fallback_date_fields])
        failed_filter_fields: set[str] = set()
        records_by_id: dict[str, tuple[dict[str, Any], date]] = {}
        missing_id_index = 0

        for current_date in iterate_report_dates(window):
            day_start, day_end = day_bounds(current_date, window)
            for filter_date_field in filter_date_fields:
                if filter_date_field in failed_filter_fields:
                    continue
                try:
                    records = fetch_day_deals(session, settings, filter_date_field, day_start, day_end, select_fields)
                except Exception as exc:
                    failed_filter_fields.add(filter_date_field)
                    data.warnings.append(
                        f"{metric_label}: не удалось загрузить сделки по полю {filter_date_field}: {safe_error_text(exc)}"
                    )
                    continue
                for record in records:
                    deal_id = str(record.get("ID") or "").strip()
                    if deal_id:
                        records_by_id.setdefault(deal_id, (record, current_date))
                    else:
                        missing_id_index += 1
                        records_by_id[f"__missing_id__{missing_id_index}"] = (record, current_date)

        for record, current_date in records_by_id.values():
            if not resolver(record.get(metric_field)):
                continue
            if metric_name == "reservations":
                event_datetime = parse_bitrix_datetime(record.get("DATE_CREATE"), settings.report_timezone)
            else:
                event_datetime = parse_bitrix_datetime(record.get(date_field), settings.report_timezone)
            if event_datetime is None:
                for fallback_date_field in fallback_date_fields:
                    event_datetime = parse_bitrix_datetime(record.get(fallback_date_field), settings.report_timezone)
                    if event_datetime is not None:
                        break
            event_date = event_datetime.date() if event_datetime else current_date
            if event_date < window.start.date() or event_date > window.end.date():
                continue
            add_fact(data, event_date, extract_assigned_user_id(record, mop_settings), metric_name, 1)


def build_meeting_facts(
    data: MopReportData,
    service: Any,
    session: requests.Session,
    settings: Settings,
    mop_settings: MopSettings,
    window: ReportWindow,
) -> None:
    if service is None:
        data.warnings.append("Встречи не посчитаны: не задан GOOGLE_SERVICE_ACCOUNT_FILE или GOOGLE_SERVICE_ACCOUNT_JSON.")
        return

    try:
        meeting_entries = build_successful_meeting_entries(service, settings)
    except ConfigError as exc:
        data.warnings.append(f"Встречи не посчитаны: {safe_error_text(exc)}")
        return

    deal_cache: dict[str, dict[str, Any]] = {}
    for entry in meeting_entries:
        if entry.meeting_date < window.start.date() or entry.meeting_date > window.end.date():
            continue
        entry_mop_name = canonical_mop_label(entry.mop_name, mop_settings)
        if entry_mop_name:
            add_fact(data, entry.meeting_date, "", "meetings", 1, mop_name=entry_mop_name)
            continue
        if not entry.deal_id:
            continue
        deal = deal_cache.get(entry.deal_id)
        if deal is None:
            try:
                deal = execute_bitrix_deal_get(session, settings, entry.deal_id)
            except Exception as exc:
                data.warnings.append(f"Не удалось получить сделку {entry.deal_id} для встречи: {safe_error_text(exc)}")
                continue
            deal_cache[entry.deal_id] = deal
        add_fact(
            data,
            entry.meeting_date,
            extract_assigned_user_id(deal, mop_settings),
            "meetings",
            1,
            mop_name=entry.mop_name,
        )


def build_call_facts(
    data: MopReportData,
    session: requests.Session,
    settings: Settings,
    mop_settings: MopSettings,
    window: ReportWindow,
) -> None:
    for current_date in iterate_report_dates(window):
        day_start, day_end = day_bounds(current_date, window)
        filters = {
            ">=CALL_START_DATE": day_start.isoformat(timespec="seconds"),
            "<=CALL_START_DATE": day_end.isoformat(timespec="seconds"),
        }
        try:
            records = fetch_paged_method(session, settings, "voximplant.statistic.get", filters)
        except Exception as exc:
            data.warnings.append(f"Звонки не посчитаны: {safe_error_text(exc)}")
            return
        for record in records:
            mop_id = str(record.get("PORTAL_USER_ID") or record.get("USER_ID") or "").strip()
            if not mop_id:
                continue
            duration = parse_number(record.get("CALL_DURATION"))
            if duration < mop_settings.call_min_duration_seconds:
                continue
            call_datetime = parse_bitrix_datetime(record.get("CALL_START_DATE"), settings.report_timezone)
            call_date = call_datetime.date() if call_datetime else current_date
            add_fact(data, call_date, mop_id, "calls", 1)
            add_fact(data, call_date, mop_id, "air_seconds", duration)


def find_plan_columns(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    column_map: dict[str, int] = {}
    matched_rows: list[int] = []
    for canonical_name, aliases in PLAN_HEADER_ALIASES.items():
        for row_index, row in enumerate(rows[:10]):
            for column_index, cell in enumerate(row):
                if normalize_text(cell) in aliases:
                    column_map[canonical_name] = column_index
                    matched_rows.append(row_index)
                    break
            if canonical_name in column_map:
                break
    if "week" not in column_map and "week_start" not in column_map:
        raise ConfigError("В листе планов не найдена колонка 'Неделя' или 'Начало недели'.")
    if "mop_id" not in column_map and "mop_name" not in column_map:
        raise ConfigError("В листе планов не найдена колонка 'МОП' или 'ID МОП'.")
    if not {"sale_plan", "meeting_plan", "reservation_plan", "mortgage_plan", "air_time_plan"} & set(
        column_map
    ):
        raise ConfigError("В листе планов не найдены плановые колонки по метрикам.")
    return max(matched_rows) if matched_rows else 0, column_map


def cell(row: list[Any], column_map: dict[str, int], name: str) -> Any:
    index = column_map.get(name)
    if index is None or index >= len(row):
        return ""
    return row[index]


def load_plan_entries(
    service: Any,
    settings: Settings,
    mop_settings: MopSettings,
    window: ReportWindow,
) -> list[PlanEntry]:
    if not mop_settings.plan_sheet_id:
        if mop_settings.plan_required:
            raise ConfigError("Set MOP_PLAN_SHEET_ID or GOOGLE_SHEET_ID for required plan loading.")
        return []
    if service is None:
        if mop_settings.plan_required:
            raise ConfigError("Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON for required plan loading.")
        return []

    try:
        sheet_title = resolve_sheet_title(service, mop_settings.plan_sheet_id, mop_settings.plan_sheet_name)
    except ConfigError:
        if mop_settings.plan_required:
            raise
        return []

    values = execute_google_request(
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=mop_settings.plan_sheet_id,
            range=f"{quote_sheet_title(sheet_title)}!A:Z",
            majorDimension="ROWS",
        )
    ).get("values", [])
    if not values:
        return []

    header_row_index, column_map = find_plan_columns(values)
    entries: list[PlanEntry] = []
    for row in values[header_row_index + 1 :]:
        week_value = cell(row, column_map, "week_start") or cell(row, column_map, "week")
        week_start = parse_week_start(week_value, window, settings.report_timezone)
        if week_start is None:
            continue
        if week_end_for_start(week_start) < window.start.date() or week_start > window.end.date():
            continue
        mop_id = str(cell(row, column_map, "mop_id") or "").strip()
        mop_name = str(cell(row, column_map, "mop_name") or "").strip()
        if not mop_id and not mop_name:
            continue
        metrics = MopMetricSet(
            sales=parse_number(cell(row, column_map, "sale_plan")),
            meetings=parse_number(cell(row, column_map, "meeting_plan")),
            reservations=parse_number(cell(row, column_map, "reservation_plan")),
            approved_mortgages=parse_number(cell(row, column_map, "mortgage_plan")),
            air_seconds=parse_duration_seconds(cell(row, column_map, "air_time_plan")),
        )
        entries.append(PlanEntry(week_start, mop_id, mop_name, metrics))
    return entries


def apply_plan_entries(data: MopReportData, plan_entries: list[PlanEntry], user_names: dict[str, str]) -> None:
    known_name_to_id = {normalize_key(name): user_id for user_id, name in user_names.items() if normalize_key(name)}
    for entry in plan_entries:
        mop_id = entry.mop_id
        mop_name = entry.mop_name
        if not mop_id and mop_name:
            mop_id = known_name_to_id.get(normalize_key(mop_name), "")
        key = key_for_mop_id(mop_id) if mop_id else key_for_mop_name(mop_name)
        if mop_id and not mop_name:
            mop_name = user_names.get(mop_id, f"Пользователь {mop_id}")
        add_plan(data, entry.week_start, key, mop_id, mop_name, entry.metrics)


def sum_metrics(items: list[MopMetricSet]) -> MopMetricSet:
    total = MopMetricSet()
    for item in items:
        total.add(item)
    return total


def row_for_metrics(sprint_label: str, mop_name: str, plan: MopMetricSet, fact: MopMetricSet) -> list[Any]:
    return [
        sprint_label,
        mop_name,
        plan.sales,
        fact.sales,
        completion_cell(plan.sales, fact.sales),
        plan.meetings,
        fact.meetings,
        completion_cell(plan.meetings, fact.meetings),
        plan.reservations,
        fact.reservations,
        completion_cell(plan.reservations, fact.reservations),
        plan.approved_mortgages,
        fact.approved_mortgages,
        completion_cell(plan.approved_mortgages, fact.approved_mortgages),
        fact.calls,
        format_duration(plan.air_seconds),
        format_duration(fact.air_seconds),
        completion_cell(plan.air_seconds, fact.air_seconds),
    ]


def build_report_rows(data: MopReportData, mop_settings: MopSettings) -> BuiltReport:
    rows: list[list[Any]] = [MOP_REPORT_HEADERS]
    group_ranges: list[tuple[int, int]] = []
    summary_rows: list[int] = []
    detail_keys: set[str] = set()
    overall_plan = MopMetricSet()
    overall_fact = MopMetricSet()
    week_starts = sorted(set(data.facts) | set(data.plans))

    for week_start in week_starts:
        keys = sorted(
            set(data.facts.get(week_start, {})) | set(data.plans.get(week_start, {})),
            key=lambda key: data.identities.get(key, MopIdentity(mop_name=key)).mop_name,
        )
        filtered_keys = []
        for key in keys:
            identity = data.identities.get(key, MopIdentity(mop_name=key))
            if mop_is_allowed(identity.mop_id, identity.mop_name, mop_settings):
                filtered_keys.append(key)
        if not filtered_keys:
            continue

        week_plan = sum_metrics([data.plans.get(week_start, {}).get(key, MopMetricSet()) for key in filtered_keys])
        week_fact = sum_metrics([data.facts.get(week_start, {}).get(key, MopMetricSet()) for key in filtered_keys])
        overall_plan.add(week_plan)
        overall_fact.add(week_fact)
        rows.append(row_for_metrics(f"Итого за спринт {format_week_label(week_start)}", "", week_plan, week_fact))
        summary_rows.append(len(rows))
        group_start = len(rows) + 1
        for key in filtered_keys:
            identity = data.identities.get(key, MopIdentity(mop_name=key))
            plan = data.plans.get(week_start, {}).get(key, MopMetricSet())
            fact = data.facts.get(week_start, {}).get(key, MopMetricSet())
            rows.append(row_for_metrics(format_week_label(week_start), identity.mop_name, plan, fact))
            detail_keys.add(key)
        if group_start <= len(rows):
            group_ranges.append((group_start, len(rows)))

    if len(rows) > 1:
        rows.append([""] * len(MOP_REPORT_HEADERS))
        rows.append(row_for_metrics("Итого за период", "", overall_plan, overall_fact))
        summary_rows.append(len(rows))

    return BuiltReport(
        rows=rows,
        group_ranges=group_ranges,
        summary_rows=summary_rows,
        detail_count=max(0, len(rows) - len(summary_rows) - 1),
        week_count=len(week_starts),
        mop_count=len(detail_keys),
    )


def build_active_deals_payload(
    data: MopReportData,
    service: Any,
    session: requests.Session,
    settings: Settings,
    mop_settings: MopSettings,
    window: ReportWindow,
) -> dict[str, Any]:
    select_fields = unique_fields(
        ACTIVE_DEAL_BASE_FIELDS
        + [
            mop_settings.assigned_field,
            settings.bitrix_approved_mortgage_field,
            settings.bitrix_reservation_field,
            mop_settings.approved_mortgage_date_field,
            mop_settings.reservation_date_field,
        ]
    )
    known_user_names = {
        identity.mop_id: identity.mop_name
        for identity in data.identities.values()
        if identity.mop_id and identity.mop_name
    }
    known_user_names.update(DEFAULT_MOP_NAMES_BY_ID)
    filter_user_ids: set[str] = set()
    for filter_value in set(mop_settings.include_users) | set(mop_settings.exclude_users):
        raw_value = filter_value[3:] if filter_value.startswith("id:") else filter_value
        if raw_value.isdigit():
            filter_user_ids.add(raw_value)

    deals: list[dict[str, Any]] = []
    category_names = fetch_deal_category_names(session, settings)
    category_ids = active_deal_category_ids(category_names, mop_settings)
    base_filters: dict[str, Any] = {
        "CLOSED": "N",
        "<=DATE_CREATE": window.end.isoformat(timespec="seconds"),
    }
    try:
        if category_ids:
            for category_id in sorted(category_ids, key=lambda item: int(item) if item.isdigit() else item):
                deals.extend(fetch_deal_list(session, settings, {**base_filters, "CATEGORY_ID": category_id}, select_fields))
        else:
            deals = fetch_deal_list(session, settings, base_filters, select_fields)
    except Exception as exc:
        data.warnings.append(f"Активные сделки не загружены: {safe_error_text(exc)}")
        return {"rows": [], "mopNames": [], "minDate": window.start.date().isoformat(), "maxDate": window.end.date().isoformat()}

    if mop_settings.active_deal_category_names and not category_ids:
        data.warnings.append(
            "Активные сделки: не найдена воронка "
            + ", ".join(mop_settings.active_deal_category_names)
            + "; сделки загружены по всем воронкам."
        )

    unique_deals: dict[str, dict[str, Any]] = {}
    for record in deals:
        deal_id = str(record.get("ID") or "").strip()
        if deal_id and deal_id not in unique_deals:
            unique_deals[deal_id] = record
    deals = list(unique_deals.values())

    assigned_user_ids = {
        extract_assigned_user_id(record, mop_settings)
        for record in deals
        if extract_assigned_user_id(record, mop_settings)
    }
    user_names = fetch_bitrix_user_names(session, settings, assigned_user_ids | filter_user_ids)
    user_names.update(known_user_names)
    stage_names = fetch_deal_stage_names(session, settings)

    meeting_events_by_deal: dict[str, list[ActiveDealActivity]] = defaultdict(list)
    if service is not None:
        try:
            for entry in build_successful_meeting_entries(service, settings):
                if entry.meeting_date <= window.end.date():
                    meeting_events_by_deal[entry.deal_id].append(
                        ActiveDealActivity(date=entry.meeting_date, kind="meetings", completed=True)
                    )
        except Exception as exc:
            data.warnings.append(f"Встречи по активным сделкам не загружены: {safe_error_text(exc)}")

    allowed_records: list[tuple[dict[str, Any], str, str, str]] = []
    for record in deals:
        deal_id = str(record.get("ID") or "").strip()
        if not deal_id:
            continue
        mop_id = extract_assigned_user_id(record, mop_settings)
        mop_name = user_names.get(mop_id, f"Пользователь {mop_id}" if mop_id else mop_settings.unknown_mop_name)
        if not mop_is_allowed(mop_id, mop_name, mop_settings):
            continue
        allowed_records.append((record, deal_id, mop_id, mop_name))

    try:
        activity_events_by_deal = fetch_deal_activity_events_batch(
            session,
            settings,
            [deal_id for _, deal_id, _, _ in allowed_records],
            window,
        )
    except Exception as exc:
        data.warnings.append(f"Активности по активным сделкам не загружены: {safe_error_text(exc)}")
        activity_events_by_deal = {}

    rows: list[dict[str, Any]] = []
    mop_names: set[str] = set()
    for record, deal_id, mop_id, mop_name in allowed_records:
        activity_events = list(activity_events_by_deal.get(deal_id, []))
        activity_events.extend(meeting_events_by_deal.get(deal_id, []))
        activity_events.sort(key=lambda event: event.date)
        last_activity_date = max((event.date for event in activity_events), default=None)

        approved = resolve_boolean_field(record.get(settings.bitrix_approved_mortgage_field))
        reservation = resolve_non_empty_field(record.get(settings.bitrix_reservation_field))
        approved_date = (
            parse_bitrix_date(record.get(mop_settings.approved_mortgage_date_field), settings.report_timezone)
            or parse_bitrix_date(record.get("DATE_CREATE"), settings.report_timezone)
        )
        reservation_date = (
            parse_bitrix_date(record.get(mop_settings.reservation_date_field), settings.report_timezone)
            or parse_bitrix_date(record.get("DATE_CREATE"), settings.report_timezone)
        )
        create_date = parse_bitrix_date(record.get("DATE_CREATE"), settings.report_timezone)
        close_date = parse_bitrix_date(record.get("CLOSEDATE"), settings.report_timezone)
        modify_date = parse_bitrix_date(record.get("DATE_MODIFY"), settings.report_timezone)
        stage_id = str(record.get("STAGE_ID") or "").strip()
        category_id = str(record.get("CATEGORY_ID") or "").strip()

        mop_names.add(mop_name)
        rows.append(
            {
                "dealId": deal_id,
                "dealUrl": bitrix_deal_url(settings, deal_id),
                "title": str(record.get("TITLE") or f"Сделка {deal_id}").strip(),
                "mopId": mop_id,
                "mopName": mop_name,
                "stageId": stage_id,
                "stageName": stage_names.get(stage_id, stage_id),
                "stageSemanticId": str(record.get("STAGE_SEMANTIC_ID") or "").strip(),
                "categoryId": category_id,
                "categoryName": category_names.get(category_id, category_id),
                "dateCreate": date_iso(create_date),
                "dateModify": date_iso(modify_date),
                "closeDate": date_iso(close_date),
                "closed": str(record.get("CLOSED") or "").upper() == "Y",
                "amount": parse_number(record.get("OPPORTUNITY")),
                "currency": str(record.get("CURRENCY_ID") or "").strip(),
                "approvedMortgage": approved,
                "approvedMortgageDate": date_iso(approved_date),
                "reservation": reservation,
                "reservationDate": date_iso(reservation_date),
                "lastActivityDate": date_iso(last_activity_date),
                "activities": [
                    {"date": event.date.isoformat(), "kind": event.kind, "completed": event.completed}
                    for event in activity_events
                ],
            }
        )

    rows.sort(key=lambda row: (row["mopName"], row["dateCreate"], int(row["dealId"]) if row["dealId"].isdigit() else row["dealId"]))
    configured_mop_names = {
        label
        for label in mop_settings.include_user_labels
        if label and not normalize_key(label).isdigit() and not normalize_key(label).startswith("id:")
    }
    return {
        "rows": rows,
        "mopNames": sorted(mop_names | configured_mop_names),
        "minDate": window.start.date().isoformat(),
        "maxDate": window.end.date().isoformat(),
    }


def build_dashboard_payload(
    data: MopReportData,
    settings: Settings,
    mop_settings: MopSettings,
    window: ReportWindow,
    active_deals_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    totals_plan = MopMetricSet()
    totals_fact = MopMetricSet()
    mop_names: set[str] = set()
    weeks: set[str] = set()

    for week_start in sorted(set(data.facts) | set(data.plans)):
        keys = sorted(
            set(data.facts.get(week_start, {})) | set(data.plans.get(week_start, {})),
            key=lambda key: data.identities.get(key, MopIdentity(mop_name=key)).mop_name,
        )
        for key in keys:
            identity = data.identities.get(key, MopIdentity(mop_name=key))
            if not mop_is_allowed(identity.mop_id, identity.mop_name, mop_settings):
                continue
            plan = data.plans.get(week_start, {}).get(key, MopMetricSet())
            fact = data.facts.get(week_start, {}).get(key, MopMetricSet())
            totals_plan.add(plan)
            totals_fact.add(fact)
            mop_names.add(identity.mop_name)
            weeks.add(week_start.isoformat())
            row = {
                "weekStart": week_start.isoformat(),
                "weekEnd": week_end_for_start(week_start).isoformat(),
                "weekLabel": format_week_label(week_start),
                "mopId": identity.mop_id,
                "mopName": identity.mop_name,
                "airTimePlan": format_duration(plan.air_seconds),
                "airTimeFact": format_duration(fact.air_seconds),
            }
            row.update(plan.as_dict("Plan"))
            row.update(fact.as_dict("Fact"))
            rows.append(row)

    generated_at = datetime.now(ZoneInfo(settings.report_timezone)).isoformat()
    configured_mop_names = {
        label
        for label in mop_settings.include_user_labels
        if label and not normalize_key(label).isdigit() and not normalize_key(label).startswith("id:")
    }
    return {
        "report": {
            "name": "Отчет по МОПам",
            "from": window.start.date().isoformat(),
            "to": window.end.date().isoformat(),
            "timezone": settings.report_timezone,
            "planSheetName": mop_settings.plan_sheet_name,
        },
        "generatedAt": generated_at,
        "filters": {
            "mopNames": sorted(mop_names | configured_mop_names),
            "weeks": sorted(weeks),
            "minWeek": min(weeks) if weeks else "",
            "maxWeek": max(weeks) if weeks else "",
        },
        "totals": {
            **totals_plan.as_dict("Plan"),
            **totals_fact.as_dict("Fact"),
            "airTimePlan": format_duration(totals_plan.air_seconds),
            "airTimeFact": format_duration(totals_fact.air_seconds),
        },
        "overview": {"mopCount": len(mop_names), "weekCount": len(weeks)},
        "activeDeals": active_deals_payload or {
            "rows": [],
            "mopNames": [],
            "minDate": window.start.date().isoformat(),
            "maxDate": window.end.date().isoformat(),
        },
        "warnings": data.warnings,
        "baseRows": rows,
    }


def write_dashboard_files(payload: dict[str, Any], dashboard_dir: Path) -> None:
    data_dir = dashboard_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    (data_dir / "mop-report-data.json").write_text(f"{json_text}\n", encoding="utf-8")
    (data_dir / "mop-report-data.js").write_text(
        f"window.MOP_REPORT_DASHBOARD_DATA = {json_text};\n",
        encoding="utf-8",
    )


def print_summary(built_report: BuiltReport, payload: dict[str, Any]) -> None:
    print("Dashboard data built: Отчет по МОПам")
    print(f"Sprints: {built_report.week_count}")
    print(f"MOPs: {built_report.mop_count}")
    print(f"Detail rows: {built_report.detail_count}")
    print(f"Dashboard rows: {len(payload.get('baseRows', []))}")
    if payload.get("warnings"):
        print("Warnings:")
        for warning in payload["warnings"]:
            print(f"- {warning}")


def main() -> int:
    try:
        args = parse_args()
        load_environment(args.env_file)
        settings = load_settings()
        mop_settings = load_mop_settings(settings)
        window = resolve_report_window(settings)
        service = build_sheets_service(settings)
        session = build_bitrix_session()

        data = MopReportData()
        build_deal_metric_facts(data, session, settings, mop_settings, window)
        build_meeting_facts(data, service, session, settings, mop_settings, window)
        build_call_facts(data, session, settings, mop_settings, window)

        user_names = fetch_bitrix_user_names(session, settings, data.user_ids)
        hydrate_fact_identities(data, user_names)
        if service is None:
            data.warnings.append("Планы не загружены: не задан GOOGLE_SERVICE_ACCOUNT_FILE или GOOGLE_SERVICE_ACCOUNT_JSON.")
        elif not mop_settings.plan_sheet_id:
            data.warnings.append("Планы не загружены: не задан MOP_PLAN_SHEET_ID или GOOGLE_SHEET_ID.")
        plan_entries = load_plan_entries(service, settings, mop_settings, window)
        apply_plan_entries(data, plan_entries, user_names)

        active_deals_payload = build_active_deals_payload(data, service, session, settings, mop_settings, window)
        built_report = build_report_rows(data, mop_settings)
        payload = build_dashboard_payload(data, settings, mop_settings, window, active_deals_payload)
        write_dashboard_files(payload, mop_settings.dashboard_dir)

        print_summary(built_report, payload)
        return 0
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except requests.Timeout as exc:
        print(f"Timeout error: {safe_error_text(exc)}", file=sys.stderr)
        return 4
    except requests.HTTPError as exc:
        print(f"HTTP error: {safe_error_text(exc)}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"Unhandled error: {safe_error_text(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
