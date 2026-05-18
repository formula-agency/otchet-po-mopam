# Отчет по МОПам

Отдельный проект для недельного план-факт отчета по каждому МОП. Проект не зависит от папки `Формула отчет`; оттуда взяты только подходы к Bitrix, Google Sheets и статичному dashboard.

## Что считает

- проведенные встречи по таблице встреч Google Sheets, только статус `Прошла успешно`
- созданные брони по полю сделки Bitrix
- одобренные ипотеки по полю сделки Bitrix
- количество звонков из `voximplant.statistic.get`
- фактическое эфирное время как сумма `CALL_DURATION`
- планы по неделям из отдельного листа Google Sheets
- итоги по каждому спринту и общий итог за период

Неделя считается с понедельника по воскресенье.

## Структура

- `scripts/sync_mop_report.py` - сбор данных и генерация dashboard data
- `dashboard/` - статичный интерфейс
- `dashboard/data/` - генерируемые `mop-report-data.json` и `mop-report-data.js`
- `.github/workflows/update-mop-report.yml` - запуск по расписанию и публикация GitHub Pages

## Локальная настройка

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Создай `bitrix.env` или `.env` по примеру `.env.example`.

Минимально нужны:

```env
BITRIX_WEBHOOK_URL=https://your-company.bitrix24.ru/rest/1/your_webhook/
GOOGLE_SERVICE_ACCOUNT_FILE=Credentials/service-account.json
MOP_PLAN_SHEET_ID=google-sheet-id-with-plans
```

## Лист планов

Планы читаются из листа `Планы МОП`. Отчет не записывает результат в Google Sheets: Google Sheets используется только как источник планов и журнала встреч.

```env
MOP_PLAN_SHEET_ID=another-google-sheet-id
MOP_PLAN_SHEET_NAME=Планы МОП
```

Поддерживаемые колонки:

| Колонка | Пример |
|---|---|
| `Неделя` или `Начало недели` | `2026-05-11` |
| `ID МОП` | `123` |
| `МОП` | `Иванов Иван` |
| `Встречи план` | `12` |
| `Брони план` | `3` |
| `Ипотеки план` | `2` |
| `Звонки план` | `180` |
| `Целевое эфирное время` | `08:00:00` |

`ID МОП` надежнее имени: по нему планы точно склеиваются с фактами из Bitrix. Если ID нет, скрипт попробует сопоставить по ФИО.

## Запуск

Запуск сборки данных для dashboard:

```powershell
python scripts/sync_mop_report.py --env-file bitrix.env
```

После запуска обновляются:

- `dashboard/data/mop-report-data.json`
- `dashboard/data/mop-report-data.js`

Dashboard открывается через `dashboard/index.html`.

## Важные настройки

- `BITRIX_APPROVED_MORTGAGE_FIELD` - поле сделки для одобренной ипотеки
- `BITRIX_RESERVATION_FIELD` - поле сделки для брони
- `MOP_DEAL_DATE_FIELD` - базовое поле даты для фактов по сделкам, по умолчанию `DATE_CREATE`
- `MOP_APPROVED_MORTGAGE_DATE_FIELD` - поле даты для ипотек, если отличается
- `MOP_RESERVATION_DATE_FIELD` - поле даты для броней, если отличается
- `MOP_ASSIGNED_FIELD` - поле ответственного, по умолчанию `ASSIGNED_BY_ID`
- `MOP_CALL_MIN_DURATION_SECONDS` - минимальная длительность звонка для учета, по умолчанию `0`
- `MOP_INCLUDE_USERS` / `MOP_EXCLUDE_USERS` - фильтр по ID или ФИО через запятую

По умолчанию отчет показывает только этих МОП:

```text
Черткова Ирина, Газисова Мария, Попова Олеся, Попова Юлия, Губайдулина Заррина, Тончу Ростислав, Погребинский Артем, Камболин Александр, Жуков Лев, Гавриленко Елена
```

Если в Bitrix ФИО хранится с отчеством, фильтр по `Фамилия Имя` все равно подойдет.

Если у webhook нет доступа к телефонии, отчет все равно построится, но в dashboard появится предупреждение, а звонки и эфир будут нулевыми.
