let data = null;

const state = {
  view: 'summary',
  mopName: 'all',
  month: '',
  sprint: '',
  search: '',
  activeDate: '',
  activeMopName: '',
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

function pair(fact, plan) {
  return `${formatNumber(fact)} / ${formatNumber(plan)}`;
}

function durationPair(fact, plan) {
  return `${formatDuration(fact)} / ${formatDuration(plan)}`;
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

function allWeekOptions() {
  const byWeek = new Map();
  for (const row of data.baseRows || []) {
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

function setDefaultPeriod() {
  const defaults = defaultPeriod();
  state.month = defaults.month;
  state.sprint = defaults.sprint;
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
  return (data.baseRows || []).filter((row) => {
    if (state.mopName !== 'all' && row.mopName !== state.mopName) return false;
    if (state.sprint && row.weekStart !== state.sprint) return false;
    if (!state.sprint && state.month && !sprintBelongsToMonth(row.weekStart, state.month)) return false;
    if (!query) return true;
    return normalizeSearch(row.mopName).includes(query);
  });
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
  for (const row of rows) {
    if (!groups.has(row.mopName)) groups.set(row.mopName, []);
    groups.get(row.mopName).push(row);
  }
  return [...groups.entries()]
    .map(([mopName, items]) => ({ mopName, ...summarizeRows(items) }))
    .sort((a, b) => b.meetingsFact - a.meetingsFact || a.mopName.localeCompare(b.mopName));
}

function renderHero(rows) {
  const summary = summarizeRows(rows);
  els.heroMops.textContent = formatNumber(new Set(rows.map((row) => row.mopName)).size);
  els.heroWeeks.textContent = formatNumber(new Set(rows.map((row) => row.weekStart)).size);
  els.heroMeetings.textContent = pair(summary.meetingsFact, summary.meetingsPlan);
  els.heroReservations.textContent = pair(summary.reservationsFact, summary.reservationsPlan);
  els.heroMortgages.textContent = pair(summary.approvedMortgagesFact, summary.approvedMortgagesPlan);
  els.heroAir.textContent = durationPair(summary.airTimeFactSeconds, summary.airTimePlanSeconds);
}

function renderKpis(rows) {
  const summary = summarizeRows(rows);
  els.kpiMeetings.textContent = pair(summary.meetingsFact, summary.meetingsPlan);
  els.kpiMeetingsRate.textContent = completion(summary.meetingsFact, summary.meetingsPlan);
  els.kpiReservations.textContent = pair(summary.reservationsFact, summary.reservationsPlan);
  els.kpiReservationsRate.textContent = completion(summary.reservationsFact, summary.reservationsPlan);
  els.kpiMortgages.textContent = pair(summary.approvedMortgagesFact, summary.approvedMortgagesPlan);
  els.kpiMortgagesRate.textContent = completion(summary.approvedMortgagesFact, summary.approvedMortgagesPlan);
  els.kpiCalls.textContent = pair(summary.callsFact, summary.callsPlan);
  els.kpiCallsRate.textContent = completion(summary.callsFact, summary.callsPlan);
  els.kpiAir.textContent = durationPair(summary.airTimeFactSeconds, summary.airTimePlanSeconds);
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
  els.selectionSummary.textContent = `Строк: ${formatNumber(rows.length)} · МОП: ${formatNumber(new Set(rows.map((row) => row.mopName)).size)} · Встречи: ${pair(summary.meetingsFact, summary.meetingsPlan)}`;
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
      <tr>
        <td>${escapeHtml(row.weekLabel)}</td>
        <td>${escapeHtml(row.mopName)}</td>
        <td>${pair(row.meetingsFact, row.meetingsPlan)} <span>${completion(row.meetingsFact, row.meetingsPlan)}</span></td>
        <td>${pair(row.reservationsFact, row.reservationsPlan)} <span>${completion(row.reservationsFact, row.reservationsPlan)}</span></td>
        <td>${pair(row.approvedMortgagesFact, row.approvedMortgagesPlan)} <span>${completion(row.approvedMortgagesFact, row.approvedMortgagesPlan)}</span></td>
        <td>${pair(row.callsFact, row.callsPlan)} <span>${completion(row.callsFact, row.callsPlan)}</span></td>
        <td>${durationPair(row.airTimeFactSeconds, row.airTimePlanSeconds)} <span>${completion(row.airTimeFactSeconds, row.airTimePlanSeconds)}</span></td>
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
    els.activeDealBody.innerHTML = '<tr class="empty-row"><td colspan="9">Нет активных сделок для выбранной даты и МОПа</td></tr>';
    return;
  }

  els.activeDealBody.innerHTML = rows.map((deal) => {
    const counters = deal.counters;
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
      label: 'Встречи факт',
      data: weeklyRows.map((row) => row.meetingsFact),
      backgroundColor: `${palette.blue}B3`,
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
      label: 'Факт',
      data: mopRows.map((row) => row.meetingsFact),
      backgroundColor: palette.blue,
      borderRadius: 4,
    },
    {
      label: 'План',
      data: mopRows.map((row) => row.meetingsPlan),
      backgroundColor: `${palette.blue}45`,
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
}

function setView(view, updateHash = true) {
  state.view = view === 'deals' ? 'deals' : 'summary';
  for (const panel of els.viewPanels) {
    const isActive = panel.dataset.viewPanel === state.view;
    panel.hidden = !isActive;
    panel.classList.toggle('is-active', isActive);
  }
  for (const link of els.viewLinks) {
    link.classList.toggle('is-active', link.dataset.viewLink === state.view);
  }
  if (updateHash && window.history) {
    window.history.replaceState(null, '', state.view === 'deals' ? '#deals' : '#summary');
  }
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
    setView(location.hash === '#deals' || location.hash === '#active-deals' ? 'deals' : 'summary', false);
  });
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
  els.activeDealDate.addEventListener('change', () => {
    state.activeDate = els.activeDealDate.value || defaultActiveDate();
    renderActiveDeals();
  });
  els.activeDealMop.addEventListener('change', () => {
    state.activeMopName = els.activeDealMop.value;
    renderActiveDeals();
  });
  els.reset.addEventListener('click', () => {
    state.mopName = 'all';
    state.search = '';
    setDefaultPeriod();
    els.mop.value = 'all';
    els.month.value = state.month;
    syncSprintSelect(true);
    els.search.value = '';
    render();
  });
  els.exportCsv.addEventListener('click', () => exportCsv(filteredRows()));
}

function init() {
  populateSelect(els.mop, data.filters?.mopNames || [], 'Все МОПы');
  setDefaultPeriod();
  setDefaultActiveDeals();
  populateSelect(els.month, monthOptions(), '', false);
  els.month.value = state.month;
  syncSprintSelect(true);
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
  setView(location.hash === '#deals' || location.hash === '#active-deals' ? 'deals' : 'summary', false);
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
