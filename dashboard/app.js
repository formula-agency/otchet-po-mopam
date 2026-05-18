let data = null;

const state = {
  mopName: 'all',
  weekFrom: 'all',
  weekTo: 'all',
  search: '',
};

const els = {
  siteHeader: document.querySelector('.site-header'),
  navLinks: [...document.querySelectorAll('.site-nav a')],
  mop: document.getElementById('filter-mop'),
  weekFrom: document.getElementById('filter-week-from'),
  weekTo: document.getElementById('filter-week-to'),
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

function populateSelect(select, options, allLabel) {
  select.innerHTML = '';
  const allOption = document.createElement('option');
  allOption.value = 'all';
  allOption.textContent = allLabel;
  select.append(allOption);

  for (const option of options) {
    const element = document.createElement('option');
    element.value = String(option.value ?? option);
    element.textContent = String(option.label ?? option);
    select.append(element);
  }
}

function weekOptions() {
  const byWeek = new Map();
  for (const row of data.baseRows || []) {
    byWeek.set(row.weekStart, row.weekLabel);
  }
  return [...byWeek.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([value, label]) => ({ value, label }));
}

function filteredRows() {
  const query = normalizeSearch(state.search);
  return (data.baseRows || []).filter((row) => {
    if (state.mopName !== 'all' && row.mopName !== state.mopName) return false;
    if (state.weekFrom !== 'all' && row.weekStart < state.weekFrom) return false;
    if (state.weekTo !== 'all' && row.weekStart > state.weekTo) return false;
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
  if (state.mopName !== 'all') chips.push(`МОП: ${state.mopName}`);
  if (state.weekFrom !== 'all') chips.push(`От: ${state.weekFrom}`);
  if (state.weekTo !== 'all') chips.push(`До: ${state.weekTo}`);
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
  const header = ['Неделя', 'МОП', 'Встречи план', 'Встречи факт', 'Брони план', 'Брони факт', 'Ипотеки план', 'Ипотеки факт', 'Звонки план', 'Звонки факт', 'Эфир план', 'Эфир факт'];
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

function bindControls() {
  els.mop.addEventListener('change', () => {
    state.mopName = els.mop.value;
    render();
  });
  els.weekFrom.addEventListener('change', () => {
    state.weekFrom = els.weekFrom.value;
    render();
  });
  els.weekTo.addEventListener('change', () => {
    state.weekTo = els.weekTo.value;
    render();
  });
  els.search.addEventListener('input', () => {
    state.search = els.search.value;
    render();
  });
  els.reset.addEventListener('click', () => {
    state.mopName = 'all';
    state.weekFrom = 'all';
    state.weekTo = 'all';
    state.search = '';
    els.mop.value = 'all';
    els.weekFrom.value = 'all';
    els.weekTo.value = 'all';
    els.search.value = '';
    render();
  });
  els.exportCsv.addEventListener('click', () => exportCsv(filteredRows()));
}

function init() {
  populateSelect(els.mop, data.filters?.mopNames || [], 'Все МОПы');
  const weeks = weekOptions();
  populateSelect(els.weekFrom, weeks, 'Все недели');
  populateSelect(els.weekTo, weeks, 'Все недели');
  bindControls();
  bindHeaderState();
  renderWarnings();
  render();
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
