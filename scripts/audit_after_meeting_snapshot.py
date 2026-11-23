"""Read-only one-off comparison of TempLab's after-meeting snapshot."""

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from mongo_formula_readonly import FormulaMongoReader


def main() -> None:
    timezone = ZoneInfo("Asia/Yekaterinburg")
    start = datetime(2026, 11, 1, tzinfo=timezone)
    end = datetime(2026, 12, 1, tzinfo=timezone)
    query = {
        "is_after_meeting": True,
        "$or": [
            {"date": {"$gte": start, "$lt": end}},
            {"date": {"$gte": "2026-11-01", "$lt": "2026-12-01"}},
            {"call_date_key": {"$gte": "2026-11-01", "$lt": "2026-12-01"}},
        ],
    }
    totals = defaultdict(lambda: {"calls": 0, "seconds": 0})
    seen = set()
    fields = set()
    with FormulaMongoReader.from_env(None, require_server_read_only=False) as reader:
        snapshot = reader.collection("analytics_page_snapshot")
        sample = snapshot.find_one({}, {"_id": 0}) or {}
        print("Snapshot sample fields: " + ", ".join(sorted(sample)))
        print("Snapshot sample dates: " + repr({
            key: value for key, value in sample.items()
            if "date" in key.lower() or "meeting" in key.lower() or "snapshot" in key.lower()
        }))
        print("Snapshot rows: " + str(snapshot.estimated_document_count()))
        print("Snapshot marked after meeting: " + str(snapshot.count_documents({"is_after_meeting": True})))
        for collection_name in ("mongo_calls", "call_analysis"):
            collection = reader.collection(collection_name)
            record = collection.find_one({}, {"_id": 0}) or {}
            print(collection_name + " fields: " + ", ".join(sorted(record)))
        for document in snapshot.find(
            query, max_time_ms=120000
        ).limit(50000):
            fields.update(document.keys())
            uid = str(document.get("call_uid") or "").strip()
            if not uid or uid in seen:
                continue
            seen.add(uid)
            name = str(document.get("user_name") or "").strip() or "<empty>"
            try:
                seconds = max(0, int(float(document.get("call_duration") or 0)))
            except (TypeError, ValueError):
                seconds = 0
            totals[name]["calls"] += 1
            totals[name]["seconds"] += seconds
    print("Snapshot fields: " + ", ".join(sorted(fields)))
    for name, value in sorted(totals.items()):
        print(f"After-meeting snapshot: {name}: {value['calls']} calls, {value['seconds']} seconds")
    print(
        "After-meeting snapshot total: "
        f"{sum(value['calls'] for value in totals.values())} calls, "
        f"{sum(value['seconds'] for value in totals.values())} seconds"
    )


if __name__ == "__main__":
    main()
