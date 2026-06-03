import json
from pathlib import Path

# Read JSON data
json_data = json.load(open('dashboard/data/mop-report-data.json', encoding='utf-8'))

# Write as JavaScript
output_path = Path('dashboard/data/mop-report-data.js')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('window.MOP_REPORT_DASHBOARD_DATA = ')
    json.dump(json_data, f, ensure_ascii=False, indent=2)
    f.write(';\n')

print(f"Updated {output_path}")
print(f"File size: {output_path.stat().st_size} bytes")
