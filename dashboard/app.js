let data = null;

const state = {
  view: 'summary',
  sidebarCollapsed: false,
  mopName: 'all',
  month: '',
  sprint: '',
  dateFrom: '',
  dateTo: '',
  search: '',
  activeDate: '',
  activeMopName: '',
  airtimeMonth: '',
  airtimeSprint: '',
  airtimeDateFrom: '',
  airtimeDateTo: '',
};

const els = {
  appFrame: document.querySelector('.app-frame'),
  sidebarToggle: document.getElementById('sidebar-toggle'),
  siteHeader: document.querySelector('.site-header'),
  navLinks: [...document.querySelectorAll('.site-nav a')],
  viewLinks: [...document.querySelectorAll('[data-view-link]')],
  viewPanels: [...document.querySelectorAll('[data-view-panel]')],
  mop: document.getElementById('filter-mop'),
  month: document.getElementById('filter-month'),
  sprint: document.getElementById('filter-sprint'),
  dateFrom: document.getElementById('filter-date-from'),
  dateTo: document.getElementById('filter-date-to'),
  search: document.getElementById('filter-search'),
  reset: document.getElementById('reset-filters'),
  activeFilters: document.getElementById('active-filters'),
  selectionSummary: document.getElementById('selection-summary'),
  heroMops: document.getElementById('hero-mops'),
  heroWeeks: document.getElementById('hero-weeks'),
  heroSales: document.getElementById('hero-sales'),
  heroMeetings: document.getElementById('hero-meetings'),
  heroReservations: document.getElementById('hero-reservations'),
  heroMortgages: document.getElementById('hero-mortgages'),
  heroAir: document.getElementById('hero-air'),
  heroTargetAfterMeeting: document.getElementById('hero-target-after-meeting'),
  kpiSales: document.getElementById('kpi-sales'),
  kpiSalesRate: document.getElementById('kpi-sales-rate'),
  kpiMeetings: document.getElementById('kpi-meetings'),
  kpiMeetingsRate: document.getElementById('kpi-meetings-rate'),
  kpiReservations: document.getElementById('kpi-reservations'),
  kpiReservationsRate: document.getElementById('kpi-reservations-rate'),
  kpiMortgages: document.getElementById('kpi-mortgages'),
  kpiMortgagesRate: document.getElementById('kpi-mortgages-rate'),
  kpiCalls: document.getElementById('kpi-calls'),
  kpiAir: document.getElementById('kpi-air'),
  kpiAirRate: document.getElementById('kpi-air-rate'),
  kpiTargetAfterMeeting: document.getElementById('kpi-target-after-meeting'),
  kpiTargetAfterMeetingRate: document.getElementById('kpi-target-after-meeting-rate'),
  detailCaption: document.getElementById('detail-caption'),
  detailBody: document.getElementById('detail-body'),
  activeDealDate: document.getElementById('active-deal-date'),
  activeDealMop: document.getElementById('active-deal-mop'),
  activeDealCaption: document.getElementById('active-deal-caption'),
  activeDealSummary: document.getElementById('active-deal-summary'),
  activeDealBody: document.getElementById('active-deal-body'),
  activeDealCount: document.getElementById('active-deal-count'),
  activeActivityCount: document.getElementById('active-activity-count'),
  activeMeetingCount: document.getElementById('active-meeting-count'),
  activeSelectionCount: document.getElementById('active-selection-count'),
  activeCallCount: document.getElementById('active-call-count'),
  activeReservationCount: document.getElementById('active-reservation-count'),
  airtimeMonth: document.getElementById('airtime-month'),
  airtimeSprint: document.getElementById('airtime-sprint'),
  airtimeDateFrom: document.getElementById('airtime-date-from'),
  airtimeDateTo: document.getElementById('airtime-date-to'),
  airtimeFreshness: document.getElementById('airtime-freshness'),
  airtimePeriodLabel: document.getElementById('airtime-period-label'),
  scoreboardSummary: document.getElementById('scoreboard-summary'),
  airtimeRows: document.getElementById('airtime-rows'),
  exportCsv: document.getElementById('export-csv'),
  warnings: document.getElementById('warnings'),
  warningsList: document.getElementById('warnings-list'),
};

const palette = {
  blue: '#2f8cff',
  green: '#5aa68f',
  violet: '#7b7af0',
  amber: '#efbd55',
  coral: '#d66b62',
};

const numberFormatter = new Intl.NumberFormat('ru-RU');
const percentFormatter = new Intl.NumberFormat('ru-RU', {
  style: 'percent',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});
const DAY_MS = 24 * 60 * 60 * 1000;
const WHOLE_MONTH_VALUE = '__whole_month__';
const POST_MEETING_AIR_PLAN_RATIO = 0.35;
const MONTH_NAMES = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
];

let weeklyChart;
let mopChart;
let factChart;

const SHARED_PLAN_REFRESH_INTERVAL_MS = 30 * 1000;
const DASHBOARD_DATA_VERSION = '20260615-2';
const SIDEBAR_COLLAPSED_STORAGE_KEY = 'mop-dashboard-sidebar-collapsed';
const AGGREGATE_PLAN_NAME = 'Общий план';
const PLAN_METRIC_FIELDS = [
  'salesPlan',
  'meetingsPlan',
  'reservationsPlan',
  'approvedMortgagesPlan',
  'airTimePlanSeconds',
];
const SCOREBOARD_METRICS = [
  { label: 'Звонки', fact: 'callsFact', kind: 'number', weight: 1 },
  { label: 'Эфир', plan: 'airTimePlanSeconds', fact: 'airTimeFactSeconds', kind: 'duration', weight: 1 / 60 },
  { label: 'Эфир после встречи', plan: 'targetMinutesAfterMeetingPlanSeconds', fact: 'targetMinutesAfterMeetingFactSeconds', kind: 'duration', weight: 1 / 60 },
  { label: 'Встречи', plan: 'meetingsPlan', fact: 'meetingsFact', kind: 'number', weight: 60 },
  { label: 'Брони', plan: 'reservationsPlan', fact: 'reservationsFact', kind: 'number', weight: 120 },
  { label: 'Ипотеки', plan: 'approvedMortgagesPlan', fact: 'approvedMortgagesFact', kind: 'number', weight: 120 },
  { label: 'Продажи', plan: 'salesPlan', fact: 'salesFact', kind: 'number', weight: 80 },
];
const ACTIVE_ACTIVITY_LABELS = {
  meetings: 'Встреча',
  approvedMortgages: 'Ипотека',
  reservations: 'Бронь',
  selections: 'Подборка',
  calls: 'Звонок',
  tasks: 'Задача',
  emails: 'Письмо',
  other: 'Другая активность',
};

function formatNumber(value) {
  return numberFormatter.format(Number(value || 0));
}

function formatDuration(seconds) {
  const safeSeconds = Math.max(0, Number(seconds || 0));
  const minutes = Math.floor(safeSeconds / 60);
  const rest = Math.floor(safeSeconds % 60);
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}

function completion(fact, plan) {
  const factValue = Number(fact || 0);
  const planValue = Number(plan || 0);
  if (planValue <= 0) return factValue > 0 ? '—' : '0%';
  return percentFormatter.format(factValue / planValue);
}

function pair(plan, fact) {
  return `${formatNumber(plan)} / ${formatNumber(fact)}`;
}

function durationPair(plan, fact) {
  return `${formatDuration(plan)} / ${formatDuration(fact)}`;
}

function postMeetingAirPlanSeconds(airPlanSeconds) {
  return Math.max(0, Math.round(Number(airPlanSeconds || 0) * POST_MEETING_AIR_PLAN_RATIO));
}

function normalizedDateRange(fromValue, toValue) {
  let from = String(fromValue || '').trim();
  let to = String(toValue || '').trim();
  if (from && to && from > to) [from, to] = [to, from];
  return { from, to };
}

function hasDateRange(fromValue, toValue) {
  const range = normalizedDateRange(fromValue, toValue);
  return Boolean(range.from || range.to);
}

function normalizeSearch(value) {
  return String(value || '').trim().toLowerCase();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function csvEscape(value) {
  const text = String(value ?? '');
  if (/[;"\r\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function normalizeNameKey(value) {
  return String(value ?? '')
    .replace(/\u00a0/g, ' ')
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/ё/g, 'е')
    .toLowerCase();
}

function normalizePlanLabel(value) {
  return normalizeNameKey(value)
    .replace(/[()]/g, ' ')
    .replace(/\s+/g, ' ');
}

function canonicalMopName(value) {
  const key = normalizeNameKey(value);
  if (!key || key === 'none' || key === 'null') return '';
  return (data.filters?.mopNames || []).find((name) => normalizeNameKey(name) === key) || '';
}

function isAggregatePlanName(value) {
  const key = normalizeNameKey(value);
  return key === 'общий план' || key === 'общий' || key === 'итого' || key === 'все мопы';
}

function parsePlanNumber(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  const text = String(value ?? '')
    .replace(/\u00a0/g, '')
    .replace(/\s+/g, '')
    .replace(',', '.')
    .replace(/[^\d.-]/g, '');
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : 0;
}

function parsePlanDurationSeconds(value) {
  const text = String(value ?? '').trim();
  const timeMatch = text.match(/^(\d{1,5}):(\d{2})(?::(\d{2}))?$/);
  if (timeMatch?.[3] !== undefined) {
    const [, hours, minutes, seconds = '0'] = timeMatch;
    return Number(hours) * 3600 + Number(minutes) * 60 + Number(seconds);
  }
  if (timeMatch) {
    const [, minutes, seconds] = timeMatch;
    return Number(minutes) * 60 + Number(seconds);
  }
  return Math.round(parsePlanNumber(value) * 60);
}

function splitMonthlyPlanValue(value, parts = 4) {
  const total = Math.max(0, Math.round(Number(value || 0)));
  const base = Math.floor(total / parts);
  const result = Array(parts).fill(base);
  result[parts - 1] += total - base * parts;
  return result;
}

function populateSelect(select, options, allLabel, includeAll = true) {
  select.innerHTML = '';
  if (includeAll) {
    const allOption = document.createElement('option');
    allOption.value = 'all';
    allOption.textContent = allLabel;
    select.append(allOption);
  }

  for (const option of options) {
    const element = document.createElement('option');
    element.value = String(option.value ?? option);
    element.textContent = String(option.label ?? option);
    select.append(element);
  }
}

function parseISODate(value) {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const [, year, month, day] = match;
  return new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
}

function todayUTC() {
  const now = new Date();
  return new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
}

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function addDays(date, days) {
  return new Date(date.getTime() + days * DAY_MS);
}

function sprintStartForDate(date) {
  const sprintDay = Math.min(22, 1 + Math.floor((date.getUTCDate() - 1) / 7) * 7);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), sprintDay));
}

function sprintEndForStart(date) {
  if (date.getUTCDate() >= 22) return addDays(nextMonth(date), -1);
  return addDays(date, 6);
}

function monthKey(date) {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
}

function firstDayOfMonth(date) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
}

function nextMonth(date) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1));
}

function shortDate(date) {
  return `${String(date.getUTCDate()).padStart(2, '0')}.${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
}

function fullDate(date) {
  return `${shortDate(date)}.${date.getUTCFullYear()}`;
}

function formatWeekLabel(weekStartValue) {
  const start = parseISODate(weekStartValue);
  if (!start) return weekStartValue;
  return `${shortDate(start)}-${fullDate(sprintEndForStart(start))}`;
}

function formatMonthLabel(key) {
  const [year, month] = key.split('-').map(Number);
  return `${MONTH_NAMES[month - 1] || key} ${year}`;
}

function parsePlanMonthDate(value) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    const shifted = new Date(value.getTime() + 12 * 60 * 60 * 1000);
    return new Date(Date.UTC(shifted.getUTCFullYear(), shifted.getUTCMonth(), 1));
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    const date = new Date(Date.UTC(1899, 11, 30) + Math.round(value) * DAY_MS);
    return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
  }

  const text = String(value ?? '').trim();
  let match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (match) return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1));

  match = text.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/);
  if (match) return new Date(Date.UTC(Number(match[3]), Number(match[2]) - 1, 1));

  return null;
}

function referenceDate() {
  return parseISODate(data.generatedAt) || parseISODate(data.report?.to) || todayUTC();
}

function actualDataDate() {
  return new Date(referenceDate().getTime() - DAY_MS);
}

function weekRange() {
  const fallback = sprintStartForDate(referenceDate());
  const rangeStart = parseISODate(data.filters?.minWeek)
    || sprintStartForDate(parseISODate(data.report?.from) || fallback);
  const endCandidates = [
    parseISODate(data.filters?.maxWeek),
    parseISODate(data.report?.to),
    referenceDate(),
    ...((data.baseRows || []).map((row) => parseISODate(row.weekStart))),
  ].filter(Boolean).map(sprintStartForDate);
  const rangeEnd = endCandidates.length
    ? new Date(Math.max(...endCandidates.map((date) => date.getTime())))
    : fallback;
  return {
    start: sprintStartForDate(rangeStart),
    end: rangeEnd,
  };
}

function sprintBelongsToMonth(weekStartValue, selectedMonth) {
  const weekStart = parseISODate(weekStartValue);
  if (!weekStart || !selectedMonth) return false;
  return monthKey(weekStart) === selectedMonth;
}

function reportRows() {
  return data.baseRows || [];
}

function dailyRows() {
  return data.dailyRows || [];
}

function rowsForDateFilters(fromValue, toValue) {
  return hasDateRange(fromValue, toValue) ? dailyRows() : reportRows();
}

function allWeekOptions() {
  const byWeek = new Map();
  for (const row of reportRows()) {
    const rowStart = parseISODate(row.weekStart);
    if (rowStart && isoDate(sprintStartForDate(rowStart)) === row.weekStart) {
      byWeek.set(row.weekStart, row.weekLabel);
    }
  }
  const range = weekRange();
  for (let monthStart = firstDayOfMonth(range.start); monthStart <= range.end; monthStart = nextMonth(monthStart)) {
    for (let day = 1; day <= 22; day += 7) {
      const current = new Date(Date.UTC(monthStart.getUTCFullYear(), monthStart.getUTCMonth(), day));
      if (current.getUTCMonth() !== monthStart.getUTCMonth()) continue;
      if (sprintEndForStart(current) < range.start || current > range.end) continue;
      const value = isoDate(current);
      if (!byWeek.has(value)) byWeek.set(value, formatWeekLabel(value));
    }
  }
  return [...byWeek.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([value, label]) => ({ value, label }));
}

function monthOptions() {
  const months = new Map();
  for (const week of allWeekOptions()) {
    const start = parseISODate(week.value);
    if (!start) continue;
    months.set(monthKey(start), formatMonthLabel(monthKey(start)));
  }
  return [...months.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([value, label]) => ({ value, label }));
}

function sprintOptionsForMonth(selectedMonth) {
  const sprintOptions = allWeekOptions()
    .filter((week) => sprintBelongsToMonth(week.value, selectedMonth))
    .map((week, index) => ({
      value: week.value,
      label: `Спринт ${index + 1} · ${week.label}`,
    }));
  return selectedMonth
    ? [{ value: WHOLE_MONTH_VALUE, label: 'Весь месяц' }, ...sprintOptions]
    : sprintOptions;
}

function sprintOnlyOptionsForMonth(selectedMonth) {
  return sprintOptionsForMonth(selectedMonth).filter((option) => option.value !== WHOLE_MONTH_VALUE);
}

function currentSprintValue() {
  return isoDate(sprintStartForDate(referenceDate()));
}

function defaultPeriod() {
  const months = monthOptions();
  const currentMonth = monthKey(referenceDate());
  const month = months.some((option) => option.value === currentMonth)
    ? currentMonth
    : (months.at(-1)?.value || currentMonth);
  return {
    month,
    sprint: defaultSprintForMonth(month),
  };
}

function defaultSprintForMonth(selectedMonth) {
  if (selectedMonth && sprintOptionsForMonth(selectedMonth).some((option) => option.value === WHOLE_MONTH_VALUE)) {
    return WHOLE_MONTH_VALUE;
  }
  const sprints = sprintOnlyOptionsForMonth(selectedMonth);
  const currentSprint = currentSprintValue();
  if (monthKey(referenceDate()) === selectedMonth && sprints.some((option) => option.value === currentSprint)) {
    return currentSprint;
  }
  const currentWeek = currentSprintValue();
  return [...sprints].reverse().find((option) => option.value <= currentWeek)?.value
    || sprints[0]?.value
    || '';
}

function syncSprintSelect(preserveSelection = false) {
  const sprints = sprintOptionsForMonth(state.month);
  if (!preserveSelection || !sprints.some((option) => option.value === state.sprint)) {
    state.sprint = defaultSprintForMonth(state.month);
  }
  populateSelect(els.sprint, sprints, '', false);
  els.sprint.value = state.sprint;
}

function syncAirTimeSprintSelect(preserveSelection = false) {
  const sprints = sprintOptionsForMonth(state.airtimeMonth);
  if (!preserveSelection || !sprints.some((option) => option.value === state.airtimeSprint)) {
    state.airtimeSprint = defaultSprintForMonth(state.airtimeMonth);
  }
  populateSelect(els.airtimeSprint, sprints, '', false);
  els.airtimeSprint.value = state.airtimeSprint;
}

function setDefaultPeriod() {
  const defaults = defaultPeriod();
  state.month = defaults.month;
  state.sprint = defaults.sprint;
  state.airtimeMonth = defaults.month;
  state.airtimeSprint = defaults.sprint;
}

function selectedOption(options, value) {
  return options.find((option) => option.value === value);
}

function rowMatchesPeriod(row, selectedMonth, selectedSprint) {
  if (selectedSprint && selectedSprint !== WHOLE_MONTH_VALUE) {
    return row.weekStart === selectedSprint;
  }
  if (selectedMonth) {
    return sprintBelongsToMonth(row.weekStart, selectedMonth);
  }
  return true;
}

function rowMatchesDateRange(row, fromValue, toValue) {
  const rowDate = String(row.date || '').slice(0, 10);
  if (!rowDate) return false;
  const range = normalizedDateRange(fromValue, toValue);
  if (range.from && rowDate < range.from) return false;
  if (range.to && rowDate > range.to) return false;
  return true;
}

function rowMatchesPeriodOrDates(row, selectedMonth, selectedSprint, fromValue, toValue) {
  if (hasDateRange(fromValue, toValue)) return rowMatchesDateRange(row, fromValue, toValue);
  return rowMatchesPeriod(row, selectedMonth, selectedSprint);
}

function activeDealsData() {
  return data.activeDeals || { rows: [], mopNames: [], minDate: data.report?.from || '', maxDate: data.report?.to || '' };
}

function activeMopOptions() {
  const names = activeDealsData().mopNames?.length
    ? activeDealsData().mopNames
    : (data.filters?.mopNames || []);
  return names.map((name) => ({ value: name, label: name }));
}

function defaultActiveDate() {
  return activeDealsData().maxDate || data.report?.to || isoDate(referenceDate());
}

function setDefaultActiveDeals() {
  const options = activeMopOptions();
  state.activeDate = defaultActiveDate();
  state.activeMopName = options.some((option) => option.value === state.mopName)
    ? state.mopName
    : (options[0]?.value || '');
}

function formatDate(value) {
  const parsed = parseISODate(value);
  return parsed ? fullDate(parsed) : '—';
}

function isDateOnOrBefore(value, selectedDate) {
  return Boolean(value) && value <= selectedDate;
}

function dealIsActiveOnDate(deal, selectedDate) {
  if (deal.dateCreate && deal.dateCreate > selectedDate) return false;
  if (!deal.closed) return true;
  const closeDate = deal.closeDate || deal.dateModify;
  return closeDate ? closeDate > selectedDate : false;
}

function emptyDealCounters() {
  return {
    meetings: 0,
    approvedMortgages: 0,
    reservations: 0,
    selections: 0,
    calls: 0,
    tasks: 0,
    emails: 0,
    other: 0,
    total: 0,
  };
}

function dealCounters(deal, selectedDate) {
  const counters = emptyDealCounters();
  if (deal.approvedMortgage && (!deal.approvedMortgageDate || isDateOnOrBefore(deal.approvedMortgageDate, selectedDate))) {
    counters.approvedMortgages += 1;
  }
  if (deal.reservation && (!deal.reservationDate || isDateOnOrBefore(deal.reservationDate, selectedDate))) {
    counters.reservations += 1;
  }

  for (const event of deal.activities || []) {
    if (!event.date || event.date > selectedDate) continue;
    const kind = counters[event.kind] === undefined ? 'other' : event.kind;
    counters[kind] += 1;
  }

  counters.total = counters.meetings
    + counters.approvedMortgages
    + counters.reservations
    + counters.selections
    + counters.calls
    + counters.tasks;
  return counters;
}

function activityKindLabel(kind) {
  return ACTIVE_ACTIVITY_LABELS[kind] || ACTIVE_ACTIVITY_LABELS.other;
}

function dealActivityTimeline(deal, selectedDate) {
  const events = (deal.activities || [])
    .filter((event) => event.date && event.date <= selectedDate)
    .map((event) => ({ date: event.date, kind: event.kind || 'other' }));

  if (deal.approvedMortgage) {
    const date = deal.approvedMortgageDate || deal.dateCreate || '';
    if (date && date <= selectedDate) events.push({ date, kind: 'approvedMortgages' });
  }

  if (deal.reservation) {
    const date = deal.reservationDate || deal.dateCreate || '';
    if (date && date <= selectedDate) events.push({ date, kind: 'reservations' });
  }

  return events.sort((a, b) => a.date.localeCompare(b.date));
}

function lastDealActivity(deal, selectedDate) {
  const events = dealActivityTimeline(deal, selectedDate);
  const lastDate = events.length ? events[events.length - 1].date : '';
  if (!lastDate) return { date: '', type: '' };

  const labels = [];
  const seen = new Set();
  for (const event of events.filter((item) => item.date === lastDate)) {
    const label = activityKindLabel(event.kind);
    if (!seen.has(label)) {
      labels.push(label);
      seen.add(label);
    }
  }

  return { date: lastDate, type: labels.join(', ') || ACTIVE_ACTIVITY_LABELS.other };
}

function filteredActiveDeals() {
  const selectedDate = state.activeDate || defaultActiveDate();
  return (activeDealsData().rows || [])
    .filter((deal) => !state.activeMopName || deal.mopName === state.activeMopName)
    .filter((deal) => dealIsActiveOnDate(deal, selectedDate))
    .map((deal) => ({ ...deal, counters: dealCounters(deal, selectedDate) }))
    .sort((a, b) => b.counters.total - a.counters.total || a.title.localeCompare(b.title));
}

function filteredRows() {
  const query = normalizeSearch(state.search);
  return rowsForDateFilters(state.dateFrom, state.dateTo).filter((row) => {
    if (state.mopName !== 'all' && row.mopName !== state.mopName) return false;
    if (!rowMatchesPeriodOrDates(row, state.month, state.sprint, state.dateFrom, state.dateTo)) return false;
    if (!query) return true;
    return normalizeSearch(row.mopName).includes(query);
  });
}

function planFieldForLabel(value) {
  const label = normalizePlanLabel(value);
  if (!label) return '';
  if (
    label === 'продажи'
    || label.includes('продажи план')
    || label.includes('план продаж')
    || label.includes('план по продаж')
    || label === 'сделки'
    || label.includes('сделки план')
    || label.includes('план сделок')
    || label.includes('план по сделкам')
    || label.includes('созданные сделки')
  ) return 'salesPlan';
  if (
    label === 'встречи'
    || label.includes('встречи план')
    || label.includes('план встреч')
    || label.includes('проведенные встречи')
  ) return 'meetingsPlan';
  if (
    label === 'брони'
    || label.includes('созданные брони')
    || label.includes('брони план')
    || label.includes('план брон')
  ) return 'reservationsPlan';
  if (
    label === 'ипотеки'
    || label.includes('ипотеки план')
    || label.includes('план ипотек')
    || (label.includes('одобрен') && label.includes('ипотек'))
  ) return 'approvedMortgagesPlan';
  if (label.includes('эфир') || label.includes('целевое эфирное время')) return 'airTimePlanSeconds';
  return '';
}

function tableCell(rows, rowIndex, columnIndex) {
  return rows[rowIndex]?.[columnIndex] ?? '';
}

function findPlanMonth(rows) {
  const labeledDateTokens = ['месяц', 'дата плана', 'период плана', 'план на'];
  for (let rowIndex = 0; rowIndex < Math.min(rows.length, 25); rowIndex += 1) {
    const row = rows[rowIndex] || [];
    for (let columnIndex = 0; columnIndex < Math.min(row.length, 8); columnIndex += 1) {
      const label = normalizePlanLabel(row[columnIndex]);
      if (!labeledDateTokens.some((token) => label.includes(token))) continue;
      for (let offset = 1; offset <= 4; offset += 1) {
        const parsed = parsePlanMonthDate(row[columnIndex + offset]);
        if (parsed) return parsed;
      }
    }
  }

  for (let rowIndex = 0; rowIndex < Math.min(rows.length, 25); rowIndex += 1) {
    const row = rows[rowIndex] || [];
    for (let columnIndex = 0; columnIndex < Math.min(row.length, 8); columnIndex += 1) {
      const parsed = parsePlanMonthDate(row[columnIndex]);
      if (parsed) return parsed;
    }
  }
  return null;
}

function isSprintHeaderRow(row) {
  const sprintColumns = [1, 4, 7, 10];
  return sprintColumns.every((columnIndex, index) => {
    const text = normalizePlanLabel(row?.[columnIndex]);
    return text.includes('спринт') && text.includes(String(index + 1));
  });
}

function findPlanColumn(row) {
  const columnIndex = (row || []).findIndex((cell) => normalizePlanLabel(cell).includes('план'));
  return columnIndex >= 0 ? columnIndex : 13;
}

function findPlanBlocks(rows) {
  const starts = [];
  for (let index = 0; index < rows.length - 1; index += 1) {
    const rawName = String(tableCell(rows, index, 1) ?? '').trim();
    if (!rawName || normalizePlanLabel(rawName).includes('спринт')) continue;
    if (isSprintHeaderRow(rows[index + 1])) starts.push(index);
  }
  return starts;
}

function sprintStartsForMonth(monthDate) {
  return [1, 8, 15, 22].map((day) => new Date(Date.UTC(
    monthDate.getUTCFullYear(),
    monthDate.getUTCMonth(),
    day,
  )));
}

function buildPlanRowsForMop(mopName, monthlyPlan, monthDate, options = {}) {
  const splitPlans = {
    salesPlan: splitMonthlyPlanValue(monthlyPlan.salesPlan),
    meetingsPlan: splitMonthlyPlanValue(monthlyPlan.meetingsPlan),
    reservationsPlan: splitMonthlyPlanValue(monthlyPlan.reservationsPlan),
    approvedMortgagesPlan: splitMonthlyPlanValue(monthlyPlan.approvedMortgagesPlan),
    airTimePlanSeconds: splitMonthlyPlanValue(monthlyPlan.airTimePlanSeconds),
  };

  return sprintStartsForMonth(monthDate).map((date, sprintIndex) => {
    const weekStart = isoDate(date);
    return {
      weekStart,
      weekLabel: formatWeekLabel(weekStart),
      mopName,
      salesPlan: splitPlans.salesPlan[sprintIndex],
      meetingsPlan: splitPlans.meetingsPlan[sprintIndex],
      reservationsPlan: splitPlans.reservationsPlan[sprintIndex],
      approvedMortgagesPlan: splitPlans.approvedMortgagesPlan[sprintIndex],
      airTimePlanSeconds: splitPlans.airTimePlanSeconds[sprintIndex],
      ...(options.aggregatePlan ? {
        aggregatePlan: true,
        manualAggregate: true,
        aggregatePlanFields: options.aggregatePlanFields || [...PLAN_METRIC_FIELDS],
      } : {}),
    };
  });
}

function planInputFields(row, header) {
  return PLAN_METRIC_FIELDS.filter((field) => {
    const columnIndex = header[field];
    if (columnIndex === undefined) return false;
    return String(row[columnIndex] ?? '').trim() !== '';
  });
}

function simplePlanHeaderMap(row) {
  const found = {};
  for (let index = 0; index < row.length; index += 1) {
    const label = normalizePlanLabel(row[index]);
    if (!label) continue;
    if (label === 'моп' || label === 'менеджер') {
      found.mopName = index;
      continue;
    }
    const field = planFieldForLabel(label);
    if (field) found[field] = index;
  }
  return found;
}

function parseSimplePlanRows(rows, monthDate) {
  let header = null;
  let headerIndex = -1;
  for (let index = 0; index < Math.min(rows.length, 40); index += 1) {
    const candidate = simplePlanHeaderMap(rows[index] || []);
    if (candidate.mopName !== undefined && PLAN_METRIC_FIELDS.some((field) => candidate[field] !== undefined)) {
      header = candidate;
      headerIndex = index;
      break;
    }
  }
  if (!header) return null;

  const importedRows = [];
  const skippedNames = new Set();
  const importedMops = new Set();
  let hasAggregatePlan = false;
  let hasIndividualMopPlans = false;

  for (let rowIndex = headerIndex + 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex] || [];
    const rawName = String(row[header.mopName] ?? '').trim();
    if (!rawName) continue;
    const aggregatePlan = isAggregatePlanName(rawName);
    const mopName = aggregatePlan ? AGGREGATE_PLAN_NAME : canonicalMopName(rawName);
    if (!mopName) {
      skippedNames.add(rawName);
      continue;
    }
    
    // Track if we have individual МОП plans
    if (!aggregatePlan) {
      hasIndividualMopPlans = true;
    }
    
    const aggregatePlanFields = aggregatePlan ? planInputFields(row, header) : [];
    if (aggregatePlan && !aggregatePlanFields.length) continue;

    const monthlyPlan = {
      salesPlan: 0,
      meetingsPlan: 0,
      reservationsPlan: 0,
      approvedMortgagesPlan: 0,
      airTimePlanSeconds: 0,
    };
    for (const field of PLAN_METRIC_FIELDS) {
      const columnIndex = header[field];
      if (columnIndex === undefined) continue;
      monthlyPlan[field] = field === 'airTimePlanSeconds'
        ? parsePlanDurationSeconds(row[columnIndex])
        : parsePlanNumber(row[columnIndex]);
    }

    if (aggregatePlan) {
      hasAggregatePlan = true;
    } else {
      importedMops.add(mopName);
    }
    importedRows.push(...buildPlanRowsForMop(mopName, monthlyPlan, monthDate, { aggregatePlan, aggregatePlanFields }));
  }

  // Validate that we have aggregate plan only
  if (hasIndividualMopPlans) {
    throw new Error('Шаблон должен содержать только строку "Общий план", без отдельных планов для каждого МОПа.');
  }
  
  if (!hasAggregatePlan) {
    throw new Error('Шаблон должен содержать строку "Общий план".');
  }

  if (!importedRows.length) return null;
  return {
    rows: importedRows,
    managerCount: 1,  // Always 1 for aggregate plan
    hasAggregatePlan: true,
    skippedNames: [...skippedNames],
  };
}

function parsePlanWorkbook(workbook, fileName) {
  const sheetName = workbook.SheetNames.find((name) => normalizeNameKey(name) === 'сводная за месяц');
  if (!sheetName) throw new Error('не найден лист "Сводная за месяц"');

  const sheet = workbook.Sheets[sheetName];
  const rows = window.XLSX.utils.sheet_to_json(sheet, { header: 1, raw: true, defval: '' });
  const monthDate = findPlanMonth(rows);
  if (!monthDate) throw new Error('не найден месяц плана');

  const simplePlan = parseSimplePlanRows(rows, monthDate);
  if (simplePlan) {
    return {
      fileName,
      month: monthKey(monthDate),
      importedAt: new Date().toISOString(),
      managerCount: simplePlan.managerCount,
      hasAggregatePlan: simplePlan.hasAggregatePlan,
      skippedNames: simplePlan.skippedNames,
      rows: simplePlan.rows,
    };
  }

  const blockStarts = findPlanBlocks(rows);
  const importedRows = [];
  const skippedNames = new Set();
  const importedMops = new Set();
  let hasAggregatePlan = false;
  let hasIndividualMopPlans = false;

  for (let blockIndex = 0; blockIndex < blockStarts.length; blockIndex += 1) {
    const start = blockStarts[blockIndex];
    const end = blockStarts[blockIndex + 1] ?? rows.length;
    const rawName = String(tableCell(rows, start, 1) ?? '').trim();
    const aggregatePlan = isAggregatePlanName(rawName);
    if (!aggregatePlan && normalizePlanLabel(rawName).startsWith('итого')) continue;
    const mopName = aggregatePlan ? AGGREGATE_PLAN_NAME : canonicalMopName(rawName);
    if (!mopName) {
      const skippedKey = normalizeNameKey(rawName);
      if (rawName && skippedKey !== 'none' && skippedKey !== 'null') skippedNames.add(rawName);
      continue;
    }

    // Track if we have individual МОП plans
    if (!aggregatePlan) {
      hasIndividualMopPlans = true;
    }

    const planColumn = findPlanColumn(rows[start + 1]);
    const valueColumn = planColumn + 1;
    const monthlyPlan = {
      salesPlan: 0,
      meetingsPlan: 0,
      reservationsPlan: 0,
      approvedMortgagesPlan: 0,
      airTimePlanSeconds: 0,
    };
    const aggregatePlanFields = [];

    for (let rowIndex = start + 2; rowIndex < end; rowIndex += 1) {
      const field = planFieldForLabel(tableCell(rows, rowIndex, planColumn));
      if (!field) continue;
      if (aggregatePlan) aggregatePlanFields.push(field);
      monthlyPlan[field] = field === 'airTimePlanSeconds'
        ? parsePlanDurationSeconds(tableCell(rows, rowIndex, valueColumn))
        : parsePlanNumber(tableCell(rows, rowIndex, valueColumn));
    }

    if (!PLAN_METRIC_FIELDS.some((field) => Number(monthlyPlan[field] || 0) > 0)) continue;
    if (aggregatePlan) {
      hasAggregatePlan = true;
    } else {
      importedMops.add(mopName);
    }
    importedRows.push(...buildPlanRowsForMop(mopName, monthlyPlan, monthDate, { aggregatePlan, aggregatePlanFields }));
  }

  // Validate that we have aggregate plan only
  if (hasIndividualMopPlans) {
    throw new Error('Шаблон должен содержать только строку "Общий план", без отдельных планов для каждого МОПа.');
  }
  
  if (!hasAggregatePlan) {
    throw new Error('Шаблон должен содержать строку "Общий план".');
  }

  if (!importedRows.length) {
    throw new Error('не найден план по МОПам из этого отчета');
  }

  return {
    fileName,
    month: monthKey(monthDate),
    importedAt: new Date().toISOString(),
    managerCount: 1,  // Always 1 for aggregate plan
    hasAggregatePlan: true,
    skippedNames: [...skippedNames],
    rows: importedRows,
  };
}

async function readPlanUploadFile(file) {
  if (!window.XLSX) throw new Error('парсер XLSX не загрузился');
  const buffer = await file.arrayBuffer();
  const workbook = window.XLSX.read(buffer, { type: 'array', cellDates: false });
  return parsePlanWorkbook(workbook, file.name);
}

function refreshPeriodControls(preserveSelection = true) {
  const months = monthOptions();
  if (!months.some((option) => option.value === state.month)) {
    state.month = months.at(-1)?.value || '';
  }
  if (!months.some((option) => option.value === state.airtimeMonth)) {
    state.airtimeMonth = state.month;
  }
  populateSelect(els.month, months, '', false);
  els.month.value = state.month;
  syncSprintSelect(preserveSelection);
  populateSelect(els.airtimeMonth, months, '', false);
  els.airtimeMonth.value = state.airtimeMonth;
  syncAirTimeSprintSelect(preserveSelection);
}

function summarizeRows(rows) {
  const factRows = rows.filter((row) => !row.aggregatePlan);
  const summary = {
    salesPlan: 0,
    salesFact: 0,
    meetingsPlan: 0,
    meetingsFact: 0,
    reservationsPlan: 0,
    reservationsFact: 0,
    approvedMortgagesPlan: 0,
    approvedMortgagesFact: 0,
    callsFact: 0,
    airTimePlanSeconds: 0,
    airTimeFactSeconds: 0,
    targetMinutesAfterMeetingPlanSeconds: 0,
    targetMinutesAfterMeetingFactSeconds: 0,
  };

  for (const field of PLAN_METRIC_FIELDS) {
    const aggregatePlanRows = rows.filter((row) => (
      row.aggregatePlan
      && (!Array.isArray(row.aggregatePlanFields) || row.aggregatePlanFields.includes(field))
    ));
    const planRows = aggregatePlanRows.length ? aggregatePlanRows : rows.filter((row) => !row.aggregatePlan);
    summary[field] = planRows.reduce((sum, row) => {
      const value = field === 'salesPlan' ? row.salesPlan ?? row.dealsPlan : row[field];
      return sum + Number(value || 0);
    }, 0);
  }

  const result = factRows.reduce((acc, row) => {
    acc.salesFact += Number(row.salesFact ?? row.dealsFact ?? 0);
    acc.meetingsFact += Number(row.meetingsFact || 0);
    acc.reservationsFact += Number(row.reservationsFact || 0);
    acc.approvedMortgagesFact += Number(row.approvedMortgagesFact || 0);
    acc.callsFact += Number(row.callsFact || 0);
    acc.airTimeFactSeconds += Number(row.airTimeFactSeconds || 0);
    acc.targetMinutesAfterMeetingFactSeconds += Number(row.targetMinutesAfterMeetingFactSeconds || 0);
    return acc;
  }, summary);
  result.targetMinutesAfterMeetingPlanSeconds = postMeetingAirPlanSeconds(result.airTimePlanSeconds);
  return result;
}

function summarizeByWeek(rows) {
  const groups = new Map();
  for (const row of rows) {
    if (!groups.has(row.weekStart)) {
      groups.set(row.weekStart, { weekStart: row.weekStart, weekLabel: row.weekLabel, rows: [] });
    }
    groups.get(row.weekStart).rows.push(row);
  }
  return [...groups.values()]
    .sort((a, b) => a.weekStart.localeCompare(b.weekStart))
    .map((group) => ({ ...group, ...summarizeRows(group.rows) }));
}

function summarizeByMop(rows) {
  const groups = new Map();
  for (const row of rows.filter((item) => !item.manualAggregate)) {
    if (!groups.has(row.mopName)) groups.set(row.mopName, []);
    groups.get(row.mopName).push(row);
  }
  return [...groups.entries()]
    .map(([mopName, items]) => ({ mopName, ...summarizeRows(items) }))
    .sort((a, b) => b.meetingsFact - a.meetingsFact || a.mopName.localeCompare(b.mopName));
}

function renderHero(rows) {
  const summary = summarizeRows(rows);
  els.heroMops.textContent = formatNumber(new Set(rows.filter((row) => !row.manualAggregate).map((row) => row.mopName)).size);
  els.heroWeeks.textContent = formatNumber(new Set(rows.map((row) => row.weekStart)).size);
  els.heroSales.textContent = pair(summary.salesPlan, summary.salesFact);
  els.heroMeetings.textContent = pair(summary.meetingsPlan, summary.meetingsFact);
  els.heroReservations.textContent = pair(summary.reservationsPlan, summary.reservationsFact);
  els.heroMortgages.textContent = pair(summary.approvedMortgagesPlan, summary.approvedMortgagesFact);
  els.heroAir.textContent = durationPair(summary.airTimePlanSeconds, summary.airTimeFactSeconds);
  els.heroTargetAfterMeeting.textContent = durationPair(
    summary.targetMinutesAfterMeetingPlanSeconds,
    summary.targetMinutesAfterMeetingFactSeconds
  );
}

function renderKpis(rows) {
  const summary = summarizeRows(rows);
  els.kpiSales.textContent = pair(summary.salesPlan, summary.salesFact);
  els.kpiSalesRate.textContent = completion(summary.salesFact, summary.salesPlan);
  els.kpiMeetings.textContent = pair(summary.meetingsPlan, summary.meetingsFact);
  els.kpiMeetingsRate.textContent = completion(summary.meetingsFact, summary.meetingsPlan);
  els.kpiReservations.textContent = pair(summary.reservationsPlan, summary.reservationsFact);
  els.kpiReservationsRate.textContent = completion(summary.reservationsFact, summary.reservationsPlan);
  els.kpiMortgages.textContent = pair(summary.approvedMortgagesPlan, summary.approvedMortgagesFact);
  els.kpiMortgagesRate.textContent = completion(summary.approvedMortgagesFact, summary.approvedMortgagesPlan);
  els.kpiCalls.textContent = formatNumber(summary.callsFact);
  els.kpiAir.textContent = durationPair(summary.airTimePlanSeconds, summary.airTimeFactSeconds);
  els.kpiAirRate.textContent = completion(summary.airTimeFactSeconds, summary.airTimePlanSeconds);
  els.kpiTargetAfterMeeting.textContent = durationPair(
    summary.targetMinutesAfterMeetingPlanSeconds,
    summary.targetMinutesAfterMeetingFactSeconds
  );
  els.kpiTargetAfterMeetingRate.textContent = completion(
    summary.targetMinutesAfterMeetingFactSeconds,
    summary.targetMinutesAfterMeetingPlanSeconds
  );
}

function renderActiveState(rows) {
  const chips = [];
  const month = selectedOption(monthOptions(), state.month);
  const sprint = selectedOption(sprintOptionsForMonth(state.month), state.sprint);
  if (state.mopName !== 'all') chips.push(`МОП: ${state.mopName}`);
  const dateRange = normalizedDateRange(state.dateFrom, state.dateTo);
  if (dateRange.from || dateRange.to) {
    const from = dateRange.from ? formatDate(dateRange.from) : 'начало';
    const to = dateRange.to ? formatDate(dateRange.to) : 'сегодня';
    chips.push(dateRange.from && dateRange.to && dateRange.from === dateRange.to
      ? `Дата: ${from}`
      : `Даты: ${from}-${to}`);
  } else {
    if (month) chips.push(`Месяц: ${month.label}`);
    if (sprint) chips.push(`Период: ${sprint.label}`);
  }
  if (normalizeSearch(state.search)) chips.push(`Поиск: ${state.search.trim()}`);

  els.activeFilters.innerHTML = chips.length
    ? chips.map((chip) => `<span class="chip">${escapeHtml(chip)}</span>`).join('')
    : '<span class="chip">Все данные</span>';

  const summary = summarizeRows(rows);
  const mopCount = new Set(rows.filter((row) => !row.manualAggregate).map((row) => row.mopName)).size;
  els.selectionSummary.textContent = `Строк: ${formatNumber(rows.length)} · МОП: ${formatNumber(mopCount)} · Продажи: ${pair(summary.salesPlan, summary.salesFact)} · Встречи: ${pair(summary.meetingsPlan, summary.meetingsFact)}`;
}

function renderDetailTable(rows) {
  els.detailCaption.textContent = `${formatNumber(rows.length)} строк`;
  if (!rows.length) {
    els.detailBody.innerHTML = '<tr class="empty-row"><td colspan="9">Нет данных</td></tr>';
    return;
  }

  els.detailBody.innerHTML = rows
    .slice()
    .sort((a, b) => (
      (a.date || a.weekStart).localeCompare(b.date || b.weekStart)
      || a.mopName.localeCompare(b.mopName)
    ))
    .map((row) => `
      <tr${row.manualAggregate ? ' class="manual-row"' : ''}>
        <td>${escapeHtml(row.dateLabel || row.weekLabel)}</td>
        <td>${escapeHtml(row.mopName)}</td>
        <td>${pair(row.salesPlan ?? row.dealsPlan, row.salesFact ?? row.dealsFact)} <span>${completion(row.salesFact ?? row.dealsFact, row.salesPlan ?? row.dealsPlan)}</span></td>
        <td>${pair(row.meetingsPlan, row.meetingsFact)} <span>${completion(row.meetingsFact, row.meetingsPlan)}</span></td>
        <td>${pair(row.reservationsPlan, row.reservationsFact)} <span>${completion(row.reservationsFact, row.reservationsPlan)}</span></td>
        <td>${pair(row.approvedMortgagesPlan, row.approvedMortgagesFact)} <span>${completion(row.approvedMortgagesFact, row.approvedMortgagesPlan)}</span></td>
        <td>${formatNumber(row.callsFact)}</td>
        <td>${durationPair(row.airTimePlanSeconds, row.airTimeFactSeconds)} <span>${completion(row.airTimeFactSeconds, row.airTimePlanSeconds)}</span></td>
        <td>${durationPair(row.targetMinutesAfterMeetingPlanSeconds, row.targetMinutesAfterMeetingFactSeconds)} <span>${completion(row.targetMinutesAfterMeetingFactSeconds, row.targetMinutesAfterMeetingPlanSeconds)}</span></td>
      </tr>
    `)
    .join('');
}

function renderActiveDeals() {
  const rows = filteredActiveDeals();
  const summary = rows.reduce((acc, row) => {
    for (const key of Object.keys(acc)) acc[key] += row.counters[key] || 0;
    return acc;
  }, emptyDealCounters());

  els.activeDealCaption.textContent = `${formatNumber(rows.length)} активных сделок`;
  els.activeDealSummary.textContent = `Дата: ${formatDate(state.activeDate)} · МОП: ${state.activeMopName || '—'} · Активностей: ${formatNumber(summary.total)}`;
  els.activeDealCount.textContent = formatNumber(rows.length);
  els.activeActivityCount.textContent = formatNumber(summary.total);
  els.activeMeetingCount.textContent = formatNumber(summary.meetings);
  els.activeSelectionCount.textContent = formatNumber(summary.selections);
  els.activeCallCount.textContent = formatNumber(summary.calls);
  els.activeReservationCount.textContent = formatNumber(summary.reservations);

  if (!rows.length) {
    els.activeDealBody.innerHTML = '<tr class="empty-row"><td colspan="11">Нет активных сделок для выбранной даты и МОПа</td></tr>';
    return;
  }

  els.activeDealBody.innerHTML = rows.map((deal) => {
    const counters = deal.counters;
    const selectedDate = state.activeDate || defaultActiveDate();
    const lastActivity = lastDealActivity(deal, selectedDate);
    const category = deal.categoryName ? `<span>${escapeHtml(deal.categoryName)}</span>` : '';
    const title = `#${deal.dealId} ${deal.title || 'Без названия'}`;
    return `
      <tr>
        <td class="deal-cell">
          <a class="deal-link" href="${escapeHtml(deal.dealUrl)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>
          ${category}
        </td>
        <td>${escapeHtml(deal.stageName || deal.stageId || '—')}</td>
        <td>${formatDate(deal.dateCreate)}</td>
        <td>${formatDate(lastActivity.date)}</td>
        <td class="activity-type-cell">${escapeHtml(lastActivity.type || '—')}</td>
        <td>${formatNumber(counters.meetings)}</td>
        <td>${formatNumber(counters.approvedMortgages)}</td>
        <td>${formatNumber(counters.reservations)}</td>
        <td>${formatNumber(counters.selections)}</td>
        <td>${formatNumber(counters.calls)}</td>
        <td>${formatNumber(counters.tasks)}</td>
      </tr>
    `;
  }).join('');
}

function emptyScoreboardRow(mopName) {
  const row = { mopName };
  for (const metric of SCOREBOARD_METRICS) {
    if (metric.plan) row[metric.plan] = 0;
    row[metric.fact] = 0;
  }
  return row;
}

function formatMetricValue(value, metric) {
  return metric.kind === 'duration' ? formatDuration(value) : formatNumber(value);
}

function metricPair(row, metric) {
  if (!metric.plan) return formatMetricValue(row[metric.fact], metric);
  return `${formatMetricValue(row[metric.plan], metric)} / ${formatMetricValue(row[metric.fact], metric)}`;
}

function scoreboardFactScore(row) {
  return SCOREBOARD_METRICS.reduce((sum, metric) => sum + Number(row[metric.fact] || 0) * metric.weight, 0);
}

function scoreboardRatio(row) {
  const ratios = SCOREBOARD_METRICS
    .filter((metric) => metric.plan && Number(row[metric.plan] || 0) > 0)
    .map((metric) => Number(row[metric.fact] || 0) / Number(row[metric.plan] || 0));
  if (!ratios.length) return null;
  return ratios.reduce((sum, value) => sum + value, 0) / ratios.length;
}

function scoreboardRows() {
  const rowsByMop = new Map((data.filters?.mopNames || []).map((name) => [name, emptyScoreboardRow(name)]));

  for (const row of rowsForDateFilters(state.airtimeDateFrom, state.airtimeDateTo)) {
    if (
      row.manualAggregate
      || !rowMatchesPeriodOrDates(
        row,
        state.airtimeMonth,
        state.airtimeSprint,
        state.airtimeDateFrom,
        state.airtimeDateTo
      )
    ) continue;
    if (!rowsByMop.has(row.mopName)) {
      rowsByMop.set(row.mopName, emptyScoreboardRow(row.mopName));
    }
    const target = rowsByMop.get(row.mopName);
    for (const metric of SCOREBOARD_METRICS) {
      if (metric.plan) target[metric.plan] += Number(row[metric.plan] || 0);
      target[metric.fact] += Number(row[metric.fact] || 0);
    }
  }

  return [...rowsByMop.values()]
    .map((row) => {
      const ratio = scoreboardRatio(row);
      const factScore = scoreboardFactScore(row);
      return {
        ...row,
        ratio,
        factScore,
      };
    })
    .sort((a, b) => (b.ratio ?? -1) - (a.ratio ?? -1) || b.factScore - a.factScore || a.mopName.localeCompare(b.mopName));
}

function scoreboardStatusClass(row) {
  if (row.ratio === null && row.factScore <= 0) return 'is-empty';
  if (row.ratio === null) return 'is-unplanned';
  if (row.ratio >= 1) return 'is-done';
  if (row.ratio >= 0.75) return 'is-close';
  return 'is-behind';
}

function scoreboardRankClass(index, total) {
  if (index === 0) return 'rank-gold';
  if (index >= Math.max(1, total - 2)) return 'rank-red';
  if (index <= 2) return 'rank-green';
  if (index <= 7) return 'rank-orange';
  return 'rank-red';
}

function renderAirTimePlanFact() {
  const rows = scoreboardRows();
  const maxFactScore = Math.max(...rows.map((row) => row.factScore), 0);
  const totals = rows.reduce((acc, row) => {
    for (const metric of SCOREBOARD_METRICS) {
      if (metric.plan) acc[metric.plan] += Number(row[metric.plan] || 0);
      acc[metric.fact] += Number(row[metric.fact] || 0);
    }
    return acc;
  }, emptyScoreboardRow('Итого'));
  const selectedSprint = selectedOption(sprintOptionsForMonth(state.airtimeMonth), state.airtimeSprint);

  if (els.airtimeFreshness) {
    els.airtimeFreshness.textContent = `Данные актуальны на ${fullDate(actualDataDate())}`;
  }
  const airtimeRange = normalizedDateRange(state.airtimeDateFrom, state.airtimeDateTo);
  if (airtimeRange.from || airtimeRange.to) {
    const from = airtimeRange.from ? formatDate(airtimeRange.from) : 'начало';
    const to = airtimeRange.to ? formatDate(airtimeRange.to) : 'сегодня';
    els.airtimePeriodLabel.textContent = airtimeRange.from && airtimeRange.to && airtimeRange.from === airtimeRange.to
      ? `Дата: ${from}`
      : `Даты: ${from}-${to}`;
  } else {
    els.airtimePeriodLabel.textContent = selectedSprint
      ? `${formatMonthLabel(state.airtimeMonth)} · ${selectedSprint.label}`
      : formatMonthLabel(state.airtimeMonth);
  }
  els.scoreboardSummary.innerHTML = SCOREBOARD_METRICS.map((metric) => `
    <article>
      <span>${escapeHtml(metric.label)}</span>
      <strong>${metricPair(totals, metric)}</strong>
      <small>${metric.plan ? completion(totals[metric.fact], totals[metric.plan]) : 'Факт'}</small>
    </article>
  `).join('');

  if (!rows.length) {
    els.airtimeRows.innerHTML = '<div class="airtime-empty">Нет данных по выбранному периоду</div>';
    return;
  }

  els.airtimeRows.innerHTML = rows.map((row, index) => {
    const progress = row.ratio !== null
      ? Math.min(100, Math.round(row.ratio * 100))
      : Math.round((row.factScore / Math.max(maxFactScore, 1)) * 100);
    const scoreLabel = row.ratio === null ? 'План не задан' : `Выполнение: ${percentFormatter.format(row.ratio)}`;
    return `
      <article class="airtime-row ${scoreboardStatusClass(row)} ${scoreboardRankClass(index, rows.length)}">
        <div class="airtime-row__rank">${index === 0 ? '<span class="airtime-row__crown" aria-hidden="true"></span>' : ''}${index + 1}</div>
        <div class="airtime-row__person">
          <strong>${escapeHtml(row.mopName)}</strong>
          <span>${escapeHtml(scoreLabel)}</span>
        </div>
        <div class="airtime-row__bar" aria-label="${escapeHtml(scoreLabel)}">
          <span style="width: ${progress}%"></span>
        </div>
        ${SCOREBOARD_METRICS.map((metric) => `
          <div class="airtime-row__metric">
            <span>${escapeHtml(metric.label)}</span>
            <strong>${metricPair(row, metric)}</strong>
          </div>
        `).join('')}
      </article>
    `;
  }).join('');
}

function ensureCharts() {
  if (!weeklyChart) {
    weeklyChart = new Chart(document.getElementById('weekly-chart'), {
      type: 'bar',
      data: { labels: [], datasets: [] },
      options: {
        maintainAspectRatio: false,
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: (value) => formatNumber(value) } },
        },
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label(context) {
                return `${context.dataset.label}: ${formatNumber(context.parsed.y)}`;
              },
            },
          },
        },
      },
    });
  }

  if (!mopChart) {
    mopChart = new Chart(document.getElementById('mop-chart'), {
      type: 'bar',
      data: { labels: [], datasets: [] },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        responsive: true,
        scales: {
          x: { beginAtZero: true, ticks: { callback: (value) => formatNumber(value) } },
          y: { grid: { display: false } },
        },
        plugins: { legend: { position: 'bottom' } },
      },
    });
  }

  if (!factChart) {
    factChart = new Chart(document.getElementById('fact-chart'), {
      type: 'doughnut',
      data: { labels: [], datasets: [] },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label(context) {
                return `${context.label}: ${formatNumber(context.parsed)}`;
              },
            },
          },
        },
      },
    });
  }
}

function renderCharts(rows) {
  ensureCharts();

  const weeklyRows = summarizeByWeek(rows);
  weeklyChart.data.labels = weeklyRows.map((row) => row.weekLabel);
  weeklyChart.data.datasets = [
    {
      label: 'Продажи факт',
      data: weeklyRows.map((row) => row.salesFact),
      backgroundColor: `${palette.coral}B3`,
      borderRadius: 4,
    },
    {
      label: 'Встречи план',
      data: weeklyRows.map((row) => row.meetingsPlan),
      borderColor: palette.blue,
      backgroundColor: palette.blue,
      type: 'line',
      tension: 0.25,
      pointRadius: 3,
    },
    {
      label: 'Встречи факт',
      data: weeklyRows.map((row) => row.meetingsFact),
      backgroundColor: `${palette.blue}B3`,
      borderRadius: 4,
    },
    {
      label: 'Брони факт',
      data: weeklyRows.map((row) => row.reservationsFact),
      backgroundColor: `${palette.green}B3`,
      borderRadius: 4,
    },
    {
      label: 'Ипотеки факт',
      data: weeklyRows.map((row) => row.approvedMortgagesFact),
      backgroundColor: `${palette.violet}B3`,
      borderRadius: 4,
    },
  ];
  weeklyChart.update();

  const mopRows = summarizeByMop(rows).slice(0, 10).reverse();
  mopChart.data.labels = mopRows.map((row) => row.mopName);
  mopChart.data.datasets = [
    {
      label: 'План',
      data: mopRows.map((row) => row.meetingsPlan),
      backgroundColor: `${palette.blue}45`,
      borderRadius: 4,
    },
    {
      label: 'Факт',
      data: mopRows.map((row) => row.meetingsFact),
      backgroundColor: palette.blue,
      borderRadius: 4,
    },
  ];
  mopChart.update();

  const summary = summarizeRows(rows);
  factChart.data.labels = ['Продажи', 'Встречи', 'Брони', 'Ипотеки', 'Звонки'];
  factChart.data.datasets = [{
    data: [summary.salesFact, summary.meetingsFact, summary.reservationsFact, summary.approvedMortgagesFact, summary.callsFact],
    backgroundColor: [palette.coral, palette.blue, palette.green, palette.violet, palette.amber],
    borderWidth: 0,
  }];
  factChart.update();
}

function renderWarnings() {
  const warnings = data.warnings || [];
  if (!warnings.length) {
    els.warnings.hidden = true;
    return;
  }
  els.warnings.hidden = false;
  els.warningsList.innerHTML = warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join('');
}

function exportCsv(rows) {
  const header = ['Период', 'МОП', 'Продажи план', 'Продажи факт', 'Встречи план', 'Встречи факт', 'Брони план', 'Брони факт', 'Ипотеки план', 'Ипотеки факт', 'Звонки факт', 'Эфир план', 'Эфир факт', 'Эфир после встречи план', 'Эфир после встречи факт'];
  const body = rows.map((row) => [
    row.dateLabel || row.weekLabel,
    row.mopName,
    row.salesPlan ?? row.dealsPlan,
    row.salesFact ?? row.dealsFact,
    row.meetingsPlan,
    row.meetingsFact,
    row.reservationsPlan,
    row.reservationsFact,
    row.approvedMortgagesPlan,
    row.approvedMortgagesFact,
    row.callsFact,
    formatDuration(row.airTimePlanSeconds),
    formatDuration(row.airTimeFactSeconds),
    formatDuration(row.targetMinutesAfterMeetingPlanSeconds),
    formatDuration(row.targetMinutesAfterMeetingFactSeconds),
  ]);
  const csv = [header, ...body].map((line) => line.map(csvEscape).join(';')).join('\r\n');
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'mop-report-export.csv';
  link.click();
  URL.revokeObjectURL(url);
}

function render() {
  const rows = filteredRows();
  renderHero(rows);
  renderKpis(rows);
  renderActiveState(rows);
  renderDetailTable(rows);
  renderCharts(rows);
  renderActiveDeals();
  if (state.view === 'airtime') renderAirTimePlanFact();
}

function setView(view, updateHash = true) {
  state.view = ['summary', 'deals', 'airtime'].includes(view) ? view : 'summary';
  for (const panel of els.viewPanels) {
    const isActive = panel.dataset.viewPanel === state.view;
    panel.hidden = !isActive;
    panel.classList.toggle('is-active', isActive);
  }
  for (const link of els.viewLinks) {
    link.classList.toggle('is-active', link.dataset.viewLink === state.view);
  }
  if (updateHash && window.history) {
    window.history.replaceState(null, '', state.view === 'summary' ? '#summary' : `#${state.view}`);
  }
  if (state.view === 'airtime') renderAirTimePlanFact();
}

function bindHeaderState() {
  if (!els.siteHeader || !els.navLinks.length) return;
  const sections = els.navLinks
    .map((link) => document.querySelector(link.getAttribute('href')))
    .filter(Boolean);

  const syncHeader = () => {
    els.siteHeader.classList.toggle('is-scrolled', window.scrollY > 16);
    const checkpoint = window.scrollY + 120;
    let activeSection = sections[0];
    for (const section of sections) {
      if (section.offsetTop <= checkpoint) activeSection = section;
    }
    for (const link of els.navLinks) {
      const target = link.getAttribute('href');
      link.classList.toggle('is-active', activeSection && `#${activeSection.id}` === target);
    }
  };

  syncHeader();
  window.addEventListener('scroll', syncHeader, { passive: true });
}

function bindViewNavigation() {
  for (const link of els.viewLinks) {
    link.addEventListener('click', () => setView(link.dataset.viewLink));
  }
  window.addEventListener('hashchange', () => {
    setView(viewFromHash(), false);
  });
}

function viewFromHash() {
  if (location.hash === '#deals' || location.hash === '#active-deals') return 'deals';
  if (location.hash === '#airtime') return 'airtime';
  return 'summary';
}

function readSidebarCollapsed() {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1';
  } catch (_error) {
    return false;
  }
}

function setSidebarCollapsed(collapsed) {
  state.sidebarCollapsed = Boolean(collapsed);
  els.appFrame?.classList.toggle('is-sidebar-collapsed', state.sidebarCollapsed);
  if (els.sidebarToggle) {
    els.sidebarToggle.setAttribute('aria-expanded', String(!state.sidebarCollapsed));
    els.sidebarToggle.setAttribute('aria-label', state.sidebarCollapsed ? 'Показать меню' : 'Скрыть меню');
    els.sidebarToggle.textContent = state.sidebarCollapsed ? '›' : '‹';
  }
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, state.sidebarCollapsed ? '1' : '0');
  } catch (_error) {
    // The control still works for the current session if storage is unavailable.
  }
}

function bindControls() {
  els.sidebarToggle?.addEventListener('click', () => {
    setSidebarCollapsed(!state.sidebarCollapsed);
  });
  els.mop.addEventListener('change', () => {
    state.mopName = els.mop.value;
    render();
  });
  els.month.addEventListener('change', () => {
    state.month = els.month.value;
    syncSprintSelect(false);
    render();
  });
  els.sprint.addEventListener('change', () => {
    state.sprint = els.sprint.value;
    render();
  });
  els.dateFrom.addEventListener('change', () => {
    state.dateFrom = els.dateFrom.value;
    render();
  });
  els.dateTo.addEventListener('change', () => {
    state.dateTo = els.dateTo.value;
    render();
  });
  els.search.addEventListener('input', () => {
    state.search = els.search.value;
    render();
  });
  els.activeDealDate.addEventListener('change', () => {
    state.activeDate = els.activeDealDate.value || defaultActiveDate();
    renderActiveDeals();
  });
  els.activeDealMop.addEventListener('change', () => {
    state.activeMopName = els.activeDealMop.value;
    renderActiveDeals();
  });
  els.airtimeMonth.addEventListener('change', () => {
    state.airtimeMonth = els.airtimeMonth.value;
    syncAirTimeSprintSelect(false);
    renderAirTimePlanFact();
  });
  els.airtimeSprint.addEventListener('change', () => {
    state.airtimeSprint = els.airtimeSprint.value;
    renderAirTimePlanFact();
  });
  els.airtimeDateFrom.addEventListener('change', () => {
    state.airtimeDateFrom = els.airtimeDateFrom.value;
    renderAirTimePlanFact();
  });
  els.airtimeDateTo.addEventListener('change', () => {
    state.airtimeDateTo = els.airtimeDateTo.value;
    renderAirTimePlanFact();
  });
  els.reset.addEventListener('click', () => {
    state.mopName = 'all';
    state.search = '';
    state.dateFrom = '';
    state.dateTo = '';
    state.airtimeDateFrom = '';
    state.airtimeDateTo = '';
    setDefaultPeriod();
    els.mop.value = 'all';
    els.month.value = state.month;
    syncSprintSelect(true);
    els.airtimeMonth.value = state.airtimeMonth;
    syncAirTimeSprintSelect(true);
    els.search.value = '';
    els.dateFrom.value = '';
    els.dateTo.value = '';
    els.airtimeDateFrom.value = '';
    els.airtimeDateTo.value = '';
    render();
  });
  els.exportCsv.addEventListener('click', () => exportCsv(filteredRows()));
}

function init() {
  setSidebarCollapsed(readSidebarCollapsed());
  populateSelect(els.mop, data.filters?.mopNames || [], 'Все МОПы');
  setDefaultPeriod();
  setDefaultActiveDeals();
  populateSelect(els.month, monthOptions(), '', false);
  els.month.value = state.month;
  syncSprintSelect(true);
  for (const input of [els.dateFrom, els.dateTo, els.airtimeDateFrom, els.airtimeDateTo]) {
    input.min = data.report?.from || '';
    input.max = data.report?.to || '';
    input.value = '';
  }
  populateSelect(els.airtimeMonth, monthOptions(), '', false);
  els.airtimeMonth.value = state.airtimeMonth;
  syncAirTimeSprintSelect(true);
  populateSelect(els.activeDealMop, activeMopOptions(), '', false);
  els.activeDealMop.value = state.activeMopName;
  els.activeDealDate.min = activeDealsData().minDate || data.report?.from || '';
  els.activeDealDate.max = activeDealsData().maxDate || data.report?.to || '';
  els.activeDealDate.value = state.activeDate;
  bindControls();
  bindViewNavigation();
  bindHeaderState();
  renderWarnings();
  render();
  setView(viewFromHash(), false);
}

async function loadData() {
  try {
    const response = await fetch(`./data/mop-report-data.json?v=${DASHBOARD_DATA_VERSION}-${Date.now()}`, {
      cache: 'no-store',
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    return window.MOP_REPORT_DASHBOARD_DATA || null;
  }
}

function sharedPlanVersion(payload) {
  return String(payload?.sharedPlans?.updatedAt || '');
}

function watchSharedPlanUpdates() {
  const currentVersion = sharedPlanVersion(data);
  window.setInterval(async () => {
    const nextData = await loadData();
    if (nextData && sharedPlanVersion(nextData) !== currentVersion) {
      window.location.reload();
    }
  }, SHARED_PLAN_REFRESH_INTERVAL_MS);
}

async function bootstrap() {
  data = await loadData();
  if (!data) {
    document.body.innerHTML = '<main class="page-shell"><section class="panel"><div class="panel-head"><h2>Нет данных</h2><p>Файл дашборда пока не сгенерирован.</p></div></section></main>';
    return;
  }
  init();
  watchSharedPlanUpdates();
}

bootstrap();
