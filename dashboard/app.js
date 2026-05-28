let data = null;

const state = {
  view: 'summary',
  mopName: 'all',
  month: '',
  sprint: '',
  search: '',
  activeDate: '',
  activeMopName: '',
  airtimeMonth: '',
  airtimeSprint: '',
  planUpload: null,
};

const els = {
  siteHeader: document.querySelector('.site-header'),
  navLinks: [...document.querySelectorAll('.site-nav a')],
  viewLinks: [...document.querySelectorAll('[data-view-link]')],
  viewPanels: [...document.querySelectorAll('[data-view-panel]')],
  mop: document.getElementById('filter-mop'),
  month: document.getElementById('filter-month'),
  sprint: document.getElementById('filter-sprint'),
  search: document.getElementById('filter-search'),
  reset: document.getElementById('reset-filters'),
  planFile: document.getElementById('plan-file-input'),
  planUploadButton: document.getElementById('plan-upload-button'),
  clearPlanUpload: document.getElementById('clear-plan-upload'),
  planUploadStatus: document.getElementById('plan-upload-status'),
  activeFilters: document.getElementById('active-filters'),
  selectionSummary: document.getElementById('selection-summary'),
  heroMops: document.getElementById('hero-mops'),
  heroWeeks: document.getElementById('hero-weeks'),
  heroMeetings: document.getElementById('hero-meetings'),
  heroReservations: document.getElementById('hero-reservations'),
  heroMortgages: document.getElementById('hero-mortgages'),
  heroAir: document.getElementById('hero-air'),
  kpiMeetings: document.getElementById('kpi-meetings'),
  kpiMeetingsRate: document.getElementById('kpi-meetings-rate'),
  kpiReservations: document.getElementById('kpi-reservations'),
  kpiReservationsRate: document.getElementById('kpi-reservations-rate'),
  kpiMortgages: document.getElementById('kpi-mortgages'),
  kpiMortgagesRate: document.getElementById('kpi-mortgages-rate'),
  kpiCalls: document.getElementById('kpi-calls'),
  kpiCallsRate: document.getElementById('kpi-calls-rate'),
  kpiAir: document.getElementById('kpi-air'),
  kpiAirRate: document.getElementById('kpi-air-rate'),
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

const PLAN_UPLOAD_STORAGE_KEY = 'mopReportPlanUpload:v1';
const PLAN_METRIC_FIELDS = [
  'meetingsPlan',
  'reservationsPlan',
  'approvedMortgagesPlan',
  'callsPlan',
  'airTimePlanSeconds',
];
const SCOREBOARD_METRICS = [
  { label: 'Встречи', plan: 'meetingsPlan', fact: 'meetingsFact', kind: 'number', weight: 60 },
  { label: 'Брони', plan: 'reservationsPlan', fact: 'reservationsFact', kind: 'number', weight: 120 },
  { label: 'Ипотеки', plan: 'approvedMortgagesPlan', fact: 'approvedMortgagesFact', kind: 'number', weight: 120 },
  { label: 'Звонки', plan: 'callsPlan', fact: 'callsFact', kind: 'number', weight: 1 },
  { label: 'Эфир', plan: 'airTimePlanSeconds', fact: 'airTimeFactSeconds', kind: 'duration', weight: 1 / 60 },
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
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const rest = Math.floor(safeSeconds % 60);
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
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

function reportRowKey(row) {
  return `${row.weekStart}|${normalizeNameKey(row.mopName)}`;
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
  const timeMatch = text.match(/^(\d{1,3}):(\d{2})(?::(\d{2}))?$/);
  if (timeMatch) {
    const [, hours, minutes, seconds = '0'] = timeMatch;
    return Number(hours) * 3600 + Number(minutes) * 60 + Number(seconds);
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
    return new Date(Date.UTC(value.getFullYear(), value.getMonth(), 1));
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

function emptyPlanRow(planRow) {
  return {
    weekStart: planRow.weekStart,
    weekLabel: planRow.weekLabel || formatWeekLabel(planRow.weekStart),
    mopName: planRow.mopName,
    meetingsPlan: 0,
    meetingsFact: 0,
    reservationsPlan: 0,
    reservationsFact: 0,
    approvedMortgagesPlan: 0,
    approvedMortgagesFact: 0,
    callsPlan: 0,
    callsFact: 0,
    airTimePlanSeconds: 0,
    airTimeFactSeconds: 0,
  };
}

function reportRows() {
  const uploadedRows = state.planUpload?.rows || [];
  if (!uploadedRows.length) return data.baseRows || [];

  const uploadedByKey = new Map(uploadedRows.map((row) => [reportRowKey(row), row]));
  const result = (data.baseRows || []).map((row) => {
    const plan = uploadedByKey.get(reportRowKey(row));
    if (!plan) return row;
    return {
      ...row,
      meetingsPlan: plan.meetingsPlan,
      reservationsPlan: plan.reservationsPlan,
      approvedMortgagesPlan: plan.approvedMortgagesPlan,
      callsPlan: plan.callsPlan,
      airTimePlanSeconds: plan.airTimePlanSeconds,
      planSource: 'uploaded',
    };
  });

  const existingKeys = new Set(result.map(reportRowKey));
  for (const plan of uploadedRows) {
    const key = reportRowKey(plan);
    if (existingKeys.has(key)) continue;
    result.push({
      ...emptyPlanRow(plan),
      ...plan,
      manualAggregate: false,
      planSource: 'uploaded',
    });
  }

  return result;
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
  return allWeekOptions()
    .filter((week) => sprintBelongsToMonth(week.value, selectedMonth))
    .map((week, index) => ({
      value: week.value,
      label: `Спринт ${index + 1} · ${week.label}`,
    }));
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
  const sprints = sprintOptionsForMonth(selectedMonth);
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
  return reportRows().filter((row) => {
    if (state.mopName !== 'all' && row.mopName !== state.mopName) return false;
    if (state.sprint && row.weekStart !== state.sprint) return false;
    if (!state.sprint && state.month && !sprintBelongsToMonth(row.weekStart, state.month)) return false;
    if (!query) return true;
    return normalizeSearch(row.mopName).includes(query);
  });
}

function planFieldForLabel(value) {
  const label = normalizePlanLabel(value);
  if (!label) return '';
  if (label.includes('проведенные встречи')) return 'meetingsPlan';
  if (
    label === 'брони'
    || label.includes('созданные брони')
    || label.includes('план по сделкам')
    || label.includes('сделки план')
    || label === 'сделки'
  ) return 'reservationsPlan';
  if (label.includes('одобрен') && label.includes('ипотек')) return 'approvedMortgagesPlan';
  if (label === 'количество звонков') return 'callsPlan';
  if (label.includes('эфир') && label.includes('время')) return 'airTimePlanSeconds';
  return '';
}

function tableCell(rows, rowIndex, columnIndex) {
  return rows[rowIndex]?.[columnIndex] ?? '';
}

function findPlanMonth(rows) {
  for (let rowIndex = 0; rowIndex < Math.min(rows.length, 25); rowIndex += 1) {
    const row = rows[rowIndex] || [];
    for (let columnIndex = 0; columnIndex < Math.min(row.length, 8); columnIndex += 1) {
      if (!normalizePlanLabel(row[columnIndex]).startsWith('месяц')) continue;
      for (let offset = 1; offset <= 4; offset += 1) {
        const parsed = parsePlanMonthDate(row[columnIndex + offset]);
        if (parsed) return parsed;
      }
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

function buildPlanRowsForMop(mopName, monthlyPlan, monthDate) {
  const splitPlans = {
    meetingsPlan: splitMonthlyPlanValue(monthlyPlan.meetingsPlan),
    reservationsPlan: splitMonthlyPlanValue(monthlyPlan.reservationsPlan),
    approvedMortgagesPlan: splitMonthlyPlanValue(monthlyPlan.approvedMortgagesPlan),
    callsPlan: splitMonthlyPlanValue(monthlyPlan.callsPlan),
    airTimePlanSeconds: splitMonthlyPlanValue(monthlyPlan.airTimePlanSeconds),
  };

  return sprintStartsForMonth(monthDate).map((date, sprintIndex) => {
    const weekStart = isoDate(date);
    return {
      weekStart,
      weekLabel: formatWeekLabel(weekStart),
      mopName,
      meetingsPlan: splitPlans.meetingsPlan[sprintIndex],
      reservationsPlan: splitPlans.reservationsPlan[sprintIndex],
      approvedMortgagesPlan: splitPlans.approvedMortgagesPlan[sprintIndex],
      callsPlan: splitPlans.callsPlan[sprintIndex],
      airTimePlanSeconds: splitPlans.airTimePlanSeconds[sprintIndex],
    };
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

  for (let rowIndex = headerIndex + 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex] || [];
    const rawName = String(row[header.mopName] ?? '').trim();
    if (!rawName) continue;
    const mopName = canonicalMopName(rawName);
    if (!mopName) {
      skippedNames.add(rawName);
      continue;
    }

    const monthlyPlan = {
      meetingsPlan: 0,
      reservationsPlan: 0,
      approvedMortgagesPlan: 0,
      callsPlan: 0,
      airTimePlanSeconds: 0,
    };
    for (const field of PLAN_METRIC_FIELDS) {
      const columnIndex = header[field];
      if (columnIndex === undefined) continue;
      monthlyPlan[field] = field === 'airTimePlanSeconds'
        ? parsePlanDurationSeconds(row[columnIndex])
        : parsePlanNumber(row[columnIndex]);
    }

    importedMops.add(mopName);
    importedRows.push(...buildPlanRowsForMop(mopName, monthlyPlan, monthDate));
  }

  if (!importedRows.length) return null;
  return {
    rows: importedRows,
    managerCount: importedMops.size,
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
      skippedNames: simplePlan.skippedNames,
      rows: simplePlan.rows,
    };
  }

  const blockStarts = findPlanBlocks(rows);
  const importedRows = [];
  const skippedNames = new Set();
  const importedMops = new Set();

  for (let blockIndex = 0; blockIndex < blockStarts.length; blockIndex += 1) {
    const start = blockStarts[blockIndex];
    const end = blockStarts[blockIndex + 1] ?? rows.length;
    const rawName = String(tableCell(rows, start, 1) ?? '').trim();
    if (normalizePlanLabel(rawName).startsWith('итого')) continue;

    const mopName = canonicalMopName(rawName);
    if (!mopName) {
      const skippedKey = normalizeNameKey(rawName);
      if (rawName && skippedKey !== 'none' && skippedKey !== 'null') skippedNames.add(rawName);
      continue;
    }

    const planColumn = findPlanColumn(rows[start + 1]);
    const valueColumn = planColumn + 1;
    const monthlyPlan = {
      meetingsPlan: 0,
      reservationsPlan: 0,
      approvedMortgagesPlan: 0,
      callsPlan: 0,
      airTimePlanSeconds: 0,
    };

    for (let rowIndex = start + 2; rowIndex < end; rowIndex += 1) {
      const field = planFieldForLabel(tableCell(rows, rowIndex, planColumn));
      if (!field) continue;
      monthlyPlan[field] = field === 'airTimePlanSeconds'
        ? parsePlanDurationSeconds(tableCell(rows, rowIndex, valueColumn))
        : parsePlanNumber(tableCell(rows, rowIndex, valueColumn));
    }

    if (!PLAN_METRIC_FIELDS.some((field) => Number(monthlyPlan[field] || 0) > 0)) continue;
    importedMops.add(mopName);
    importedRows.push(...buildPlanRowsForMop(mopName, monthlyPlan, monthDate));
  }

  if (!importedRows.length) {
    throw new Error('не найден план по МОПам из этого отчета');
  }

  return {
    fileName,
    month: monthKey(monthDate),
    importedAt: new Date().toISOString(),
    managerCount: importedMops.size,
    skippedNames: [...skippedNames],
    rows: importedRows,
  };
}

async function readPlanUploadFile(file) {
  if (!window.XLSX) throw new Error('парсер XLSX не загрузился');
  const buffer = await file.arrayBuffer();
  const workbook = window.XLSX.read(buffer, { type: 'array', cellDates: true });
  return parsePlanWorkbook(workbook, file.name);
}

function normalizeStoredPlanUpload(upload) {
  if (!upload || !Array.isArray(upload.rows) || !upload.rows.length) return null;
  const rows = upload.rows
    .filter((row) => row.weekStart && row.mopName)
    .map((row) => ({
      weekStart: row.weekStart,
      weekLabel: row.weekLabel || formatWeekLabel(row.weekStart),
      mopName: row.mopName,
      meetingsPlan: parsePlanNumber(row.meetingsPlan),
      reservationsPlan: parsePlanNumber(row.reservationsPlan),
      approvedMortgagesPlan: parsePlanNumber(row.approvedMortgagesPlan),
      callsPlan: parsePlanNumber(row.callsPlan),
      airTimePlanSeconds: parsePlanNumber(row.airTimePlanSeconds),
    }));
  if (!rows.length) return null;
  return {
    fileName: upload.fileName || 'Загруженный файл',
    month: upload.month || monthKey(parseISODate(rows[0].weekStart)),
    importedAt: upload.importedAt || '',
    managerCount: Number(upload.managerCount || new Set(rows.map((row) => row.mopName)).size),
    skippedNames: Array.isArray(upload.skippedNames) ? upload.skippedNames : [],
    rows,
  };
}

function loadStoredPlanUpload() {
  try {
    return normalizeStoredPlanUpload(JSON.parse(localStorage.getItem(PLAN_UPLOAD_STORAGE_KEY)));
  } catch (error) {
    return null;
  }
}

function savePlanUpload(upload) {
  try {
    localStorage.setItem(PLAN_UPLOAD_STORAGE_KEY, JSON.stringify(upload));
  } catch (error) {
    // The dashboard still works for the current session if browser storage is unavailable.
  }
}

function removeStoredPlanUpload() {
  try {
    localStorage.removeItem(PLAN_UPLOAD_STORAGE_KEY);
  } catch (error) {
    // No action needed.
  }
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

function renderPlanUploadStatus(message = '') {
  if (message) {
    els.planUploadStatus.textContent = message;
    return;
  }

  if (!state.planUpload) {
    els.planUploadStatus.textContent = 'План не загружен';
    els.clearPlanUpload.hidden = true;
    return;
  }

  const skippedCount = state.planUpload.skippedNames?.length || 0;
  const skippedText = skippedCount ? ` · пропущено: ${formatNumber(skippedCount)}` : '';
  els.planUploadStatus.textContent = `${formatMonthLabel(state.planUpload.month)} · МОП: ${formatNumber(state.planUpload.managerCount)}${skippedText}`;
  els.clearPlanUpload.hidden = false;
}

function applyPlanUpload(upload, focusMonth = false) {
  state.planUpload = upload;
  if (focusMonth && upload.month) {
    state.month = upload.month;
    state.sprint = defaultSprintForMonth(state.month);
    state.airtimeMonth = upload.month;
    state.airtimeSprint = defaultSprintForMonth(state.airtimeMonth);
  }
  refreshPeriodControls(true);
  renderPlanUploadStatus();
  render();
}

function clearPlanUpload() {
  state.planUpload = null;
  removeStoredPlanUpload();
  refreshPeriodControls(false);
  renderPlanUploadStatus();
  render();
}

function summarizeRows(rows) {
  return rows.reduce((acc, row) => {
    acc.meetingsPlan += Number(row.meetingsPlan || 0);
    acc.meetingsFact += Number(row.meetingsFact || 0);
    acc.reservationsPlan += Number(row.reservationsPlan || 0);
    acc.reservationsFact += Number(row.reservationsFact || 0);
    acc.approvedMortgagesPlan += Number(row.approvedMortgagesPlan || 0);
    acc.approvedMortgagesFact += Number(row.approvedMortgagesFact || 0);
    acc.callsPlan += Number(row.callsPlan || 0);
    acc.callsFact += Number(row.callsFact || 0);
    acc.airTimePlanSeconds += Number(row.airTimePlanSeconds || 0);
    acc.airTimeFactSeconds += Number(row.airTimeFactSeconds || 0);
    return acc;
  }, {
    meetingsPlan: 0,
    meetingsFact: 0,
    reservationsPlan: 0,
    reservationsFact: 0,
    approvedMortgagesPlan: 0,
    approvedMortgagesFact: 0,
    callsPlan: 0,
    callsFact: 0,
    airTimePlanSeconds: 0,
    airTimeFactSeconds: 0,
  });
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
  els.heroMeetings.textContent = pair(summary.meetingsPlan, summary.meetingsFact);
  els.heroReservations.textContent = pair(summary.reservationsPlan, summary.reservationsFact);
  els.heroMortgages.textContent = pair(summary.approvedMortgagesPlan, summary.approvedMortgagesFact);
  els.heroAir.textContent = durationPair(summary.airTimePlanSeconds, summary.airTimeFactSeconds);
}

function renderKpis(rows) {
  const summary = summarizeRows(rows);
  els.kpiMeetings.textContent = pair(summary.meetingsPlan, summary.meetingsFact);
  els.kpiMeetingsRate.textContent = completion(summary.meetingsFact, summary.meetingsPlan);
  els.kpiReservations.textContent = pair(summary.reservationsPlan, summary.reservationsFact);
  els.kpiReservationsRate.textContent = completion(summary.reservationsFact, summary.reservationsPlan);
  els.kpiMortgages.textContent = pair(summary.approvedMortgagesPlan, summary.approvedMortgagesFact);
  els.kpiMortgagesRate.textContent = completion(summary.approvedMortgagesFact, summary.approvedMortgagesPlan);
  els.kpiCalls.textContent = pair(summary.callsPlan, summary.callsFact);
  els.kpiCallsRate.textContent = completion(summary.callsFact, summary.callsPlan);
  els.kpiAir.textContent = durationPair(summary.airTimePlanSeconds, summary.airTimeFactSeconds);
  els.kpiAirRate.textContent = completion(summary.airTimeFactSeconds, summary.airTimePlanSeconds);
}

function renderActiveState(rows) {
  const chips = [];
  const month = selectedOption(monthOptions(), state.month);
  const sprint = selectedOption(sprintOptionsForMonth(state.month), state.sprint);
  if (state.mopName !== 'all') chips.push(`МОП: ${state.mopName}`);
  if (month) chips.push(`Месяц: ${month.label}`);
  if (sprint) chips.push(`Спринт: ${sprint.label}`);
  if (normalizeSearch(state.search)) chips.push(`Поиск: ${state.search.trim()}`);

  els.activeFilters.innerHTML = chips.length
    ? chips.map((chip) => `<span class="chip">${escapeHtml(chip)}</span>`).join('')
    : '<span class="chip">Все данные</span>';

  const summary = summarizeRows(rows);
  const mopCount = new Set(rows.filter((row) => !row.manualAggregate).map((row) => row.mopName)).size;
  els.selectionSummary.textContent = `Строк: ${formatNumber(rows.length)} · МОП: ${formatNumber(mopCount)} · Встречи: ${pair(summary.meetingsPlan, summary.meetingsFact)}`;
}

function renderDetailTable(rows) {
  els.detailCaption.textContent = `${formatNumber(rows.length)} строк`;
  if (!rows.length) {
    els.detailBody.innerHTML = '<tr class="empty-row"><td colspan="7">Нет данных</td></tr>';
    return;
  }

  els.detailBody.innerHTML = rows
    .slice()
    .sort((a, b) => a.weekStart.localeCompare(b.weekStart) || a.mopName.localeCompare(b.mopName))
    .map((row) => `
      <tr${row.manualAggregate ? ' class="manual-row"' : ''}>
        <td>${escapeHtml(row.weekLabel)}</td>
        <td>${escapeHtml(row.mopName)}</td>
        <td>${pair(row.meetingsPlan, row.meetingsFact)} <span>${completion(row.meetingsFact, row.meetingsPlan)}</span></td>
        <td>${pair(row.reservationsPlan, row.reservationsFact)} <span>${completion(row.reservationsFact, row.reservationsPlan)}</span></td>
        <td>${pair(row.approvedMortgagesPlan, row.approvedMortgagesFact)} <span>${completion(row.approvedMortgagesFact, row.approvedMortgagesPlan)}</span></td>
        <td>${pair(row.callsPlan, row.callsFact)} <span>${completion(row.callsFact, row.callsPlan)}</span></td>
        <td>${durationPair(row.airTimePlanSeconds, row.airTimeFactSeconds)} <span>${completion(row.airTimeFactSeconds, row.airTimePlanSeconds)}</span></td>
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
    row[metric.plan] = 0;
    row[metric.fact] = 0;
  }
  return row;
}

function formatMetricValue(value, metric) {
  return metric.kind === 'duration' ? formatDuration(value) : formatNumber(value);
}

function metricPair(row, metric) {
  return `${formatMetricValue(row[metric.plan], metric)} / ${formatMetricValue(row[metric.fact], metric)}`;
}

function scoreboardFactScore(row) {
  return SCOREBOARD_METRICS.reduce((sum, metric) => sum + Number(row[metric.fact] || 0) * metric.weight, 0);
}

function scoreboardRatio(row) {
  const ratios = SCOREBOARD_METRICS
    .filter((metric) => Number(row[metric.plan] || 0) > 0)
    .map((metric) => Number(row[metric.fact] || 0) / Number(row[metric.plan] || 0));
  if (!ratios.length) return null;
  return ratios.reduce((sum, value) => sum + value, 0) / ratios.length;
}

function scoreboardRows() {
  const rowsByMop = new Map((data.filters?.mopNames || []).map((name) => [name, emptyScoreboardRow(name)]));

  for (const row of reportRows()) {
    if (row.manualAggregate || row.weekStart !== state.airtimeSprint) continue;
    if (!rowsByMop.has(row.mopName)) {
      rowsByMop.set(row.mopName, emptyScoreboardRow(row.mopName));
    }
    const target = rowsByMop.get(row.mopName);
    for (const metric of SCOREBOARD_METRICS) {
      target[metric.plan] += Number(row[metric.plan] || 0);
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

function renderAirTimePlanFact() {
  const rows = scoreboardRows();
  const maxFactScore = Math.max(...rows.map((row) => row.factScore), 0);
  const totals = rows.reduce((acc, row) => {
    for (const metric of SCOREBOARD_METRICS) {
      acc[metric.plan] += Number(row[metric.plan] || 0);
      acc[metric.fact] += Number(row[metric.fact] || 0);
    }
    return acc;
  }, emptyScoreboardRow('Итого'));
  const selectedSprint = selectedOption(sprintOptionsForMonth(state.airtimeMonth), state.airtimeSprint);

  els.airtimePeriodLabel.textContent = selectedSprint
    ? `${formatMonthLabel(state.airtimeMonth)} · ${selectedSprint.label}`
    : formatMonthLabel(state.airtimeMonth);
  els.scoreboardSummary.innerHTML = SCOREBOARD_METRICS.map((metric) => `
    <article>
      <span>${escapeHtml(metric.label)}</span>
      <strong>${metricPair(totals, metric)}</strong>
      <small>${completion(totals[metric.fact], totals[metric.plan])}</small>
    </article>
  `).join('');

  if (!rows.length) {
    els.airtimeRows.innerHTML = '<div class="airtime-empty">Нет данных по выбранному спринту</div>';
    return;
  }

  els.airtimeRows.innerHTML = rows.map((row, index) => {
    const progress = row.ratio !== null
      ? Math.min(100, Math.round(row.ratio * 100))
      : Math.round((row.factScore / Math.max(maxFactScore, 1)) * 100);
    const scoreLabel = row.ratio === null ? 'План не задан' : `Выполнение: ${percentFormatter.format(row.ratio)}`;
    return `
      <article class="airtime-row ${scoreboardStatusClass(row)}">
        <div class="airtime-row__rank">${index + 1}</div>
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
  factChart.data.labels = ['Встречи', 'Брони', 'Ипотеки', 'Звонки'];
  factChart.data.datasets = [{
    data: [summary.meetingsFact, summary.reservationsFact, summary.approvedMortgagesFact, summary.callsFact],
    backgroundColor: [palette.blue, palette.green, palette.violet, palette.amber],
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
  const header = ['Спринт', 'МОП', 'Встречи план', 'Встречи факт', 'Брони план', 'Брони факт', 'Ипотеки план', 'Ипотеки факт', 'Звонки план', 'Звонки факт', 'Эфир план', 'Эфир факт'];
  const body = rows.map((row) => [
    row.weekLabel,
    row.mopName,
    row.meetingsPlan,
    row.meetingsFact,
    row.reservationsPlan,
    row.reservationsFact,
    row.approvedMortgagesPlan,
    row.approvedMortgagesFact,
    row.callsPlan,
    row.callsFact,
    formatDuration(row.airTimePlanSeconds),
    formatDuration(row.airTimeFactSeconds),
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

function bindControls() {
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
  els.search.addEventListener('input', () => {
    state.search = els.search.value;
    render();
  });
  els.planUploadButton.addEventListener('click', () => {
    els.planFile.click();
  });
  els.planFile.addEventListener('change', async () => {
    const file = els.planFile.files?.[0];
    if (!file) return;
    renderPlanUploadStatus('Читаю план...');
    try {
      const upload = await readPlanUploadFile(file);
      savePlanUpload(upload);
      applyPlanUpload(upload, true);
    } catch (error) {
      renderPlanUploadStatus(`Не удалось загрузить план: ${error.message}`);
    } finally {
      els.planFile.value = '';
    }
  });
  els.clearPlanUpload.addEventListener('click', clearPlanUpload);
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
  els.reset.addEventListener('click', () => {
    state.mopName = 'all';
    state.search = '';
    setDefaultPeriod();
    els.mop.value = 'all';
    els.month.value = state.month;
    syncSprintSelect(true);
    els.airtimeMonth.value = state.airtimeMonth;
    syncAirTimeSprintSelect(true);
    els.search.value = '';
    render();
  });
  els.exportCsv.addEventListener('click', () => exportCsv(filteredRows()));
}

function init() {
  state.planUpload = loadStoredPlanUpload();
  populateSelect(els.mop, data.filters?.mopNames || [], 'Все МОПы');
  setDefaultPeriod();
  setDefaultActiveDeals();
  populateSelect(els.month, monthOptions(), '', false);
  els.month.value = state.month;
  syncSprintSelect(true);
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
  renderPlanUploadStatus();
  render();
  setView(viewFromHash(), false);
}

async function loadData() {
  try {
    const response = await fetch('./data/mop-report-data.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    return window.MOP_REPORT_DASHBOARD_DATA || null;
  }
}

async function bootstrap() {
  data = await loadData();
  if (!data) {
    document.body.innerHTML = '<main class="page-shell"><section class="panel"><div class="panel-head"><h2>Нет данных</h2><p>Файл дашборда пока не сгенерирован.</p></div></section></main>';
    return;
  }
  init();
}

bootstrap();
