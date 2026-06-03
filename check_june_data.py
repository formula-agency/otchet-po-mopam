import json
data = json.load(open('dashboard/data/mop-report-data.json', encoding='utf-8'))
june_rows = [r for r in data.get('baseRows', []) if '2026-06' in r.get('weekStart', '')]
print('June rows count:', len(june_rows))
print('\nFirst 20 rows:')
for r in june_rows[:20]:
    print(f"Week: {r.get('weekStart')}, MOP: {r.get('mopName')[:20]}, MopId: '{r.get('mopId')}', Sales: {r.get('salesPlan')}, Meetings: {r.get('meetingsPlan')}, Shared: {r.get('sharedPlanOnlyRow', False)}")
