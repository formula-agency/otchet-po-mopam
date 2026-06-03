import json

# Check shared-plans.json
shared_plans = json.load(open('manual-data/shared-plans.json', encoding='utf-8'))
june_plan = shared_plans.get('months', {}).get('2026-06', {})
print("=== Проверка shared-plans.json (June) ===")
print(f"hasAggregatePlan: {june_plan.get('hasAggregatePlan')}")
print(f"managerCount: {june_plan.get('managerCount')}")
print(f"Количество плана-строк: {len(june_plan.get('plans', []))}")
if june_plan.get('plans'):
    plan = june_plan['plans'][0]
    print(f"Первый план (должен быть 'Общий план'):")
    print(f"  - mopName: {plan.get('mopName')}")
    print(f"  - aggregatePlan: {plan.get('aggregatePlan')}")
    print(f"  - salesPlan: {plan.get('salesPlan')}")
    print(f"  - meetingsPlan: {plan.get('meetingsPlan')}")

# Check dashboard data
data = json.load(open('dashboard/data/mop-report-data.json', encoding='utf-8'))
june_rows = [r for r in data.get('baseRows', []) if '2026-06' in r.get('weekStart', '')]

print("\n=== Проверка dashboard JSON (June rows) ===")
print(f"Всего строк на Июнь: {len(june_rows)}")

by_week = {}
for r in june_rows:
    week = r.get('weekStart')
    if week not in by_week:
        by_week[week] = 0
    by_week[week] += 1

for week in sorted(by_week.keys()):
    print(f"  - {week}: {by_week[week]} МОПов")

print(f"\nПроверка представленности МОПов в первой неделе:")
week1_rows = [r for r in june_rows if r.get('weekStart') == '2026-06-01']
mop_ids = set()
for r in week1_rows:
    mop_ids.add(r.get('mopId', 'EMPTY'))

print(f"Количество уникальных mopId: {len(mop_ids)}")
print(f"Есть ли пустые mopId: {'EMPTY' in mop_ids}")

print(f"\nПервые 3 МОПа в первую неделю Июня:")
for r in week1_rows[:3]:
    print(f"  - {r.get('mopName')}: mopId='{r.get('mopId')}', meetings={r.get('meetingsPlan')}")
