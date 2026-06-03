import json
data = json.load(open('dashboard/data/mop-report-data.json', encoding='utf-8'))
june_rows = [r for r in data.get('baseRows', []) if '2026-06' in r.get('weekStart', '')]
print(f"Total June rows: {len(june_rows)}")
if june_rows:
    print("\nSample June rows with plans:")
    plan_rows = [r for r in june_rows if r.get('sharedPlanOnlyRow')]
    for r in plan_rows[:5]:
        print(f"  Week {r.get('weekStart')}: {r.get('mopName')[:20]}, mopId={r.get('mopId')}, meetings={r.get('meetingsPlan')}")
    print(f"\nTotal plan rows for June: {len(plan_rows)}")
