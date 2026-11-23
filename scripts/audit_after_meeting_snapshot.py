"""Read-only one-off comparison of TempLab's after-meeting snapshot."""

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from mongo_formula_readonly import FormulaMongoReader
from sync_mop_report import (
    build_mongo_target_after_meeting_pipeline,
    calculate_target_after_meeting_entries,
)


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
        print("Snapshot month distribution: " + repr(list(snapshot.aggregate([
            {"$group": {
                "_id": {"month": {"$substr": ["$call_date_key", 0, 7]}, "after": "$is_after_meeting"},
                "count": {"$sum": 1},
                "seconds": {"$sum": {"$convert": {"input": "$call_duration", "to": "int", "onError": 0, "onNull": 0}}},
            }},
            {"$sort": {"_id.month": 1, "_id.after": 1}},
        ], maxTimeMS=120000))))
        for collection_name in ("mongo_calls", "call_analysis"):
            collection = reader.collection(collection_name)
            record = collection.find_one({}, {"_id": 0}) or {}
            print(collection_name + " fields: " + ", ".join(sorted(record)))
        meeting_collection = reader.collection("okk_meetings_check")
        meeting_sample = meeting_collection.find_one({}, {"_id": 0}) or {}
        print("Meetings fields: " + ", ".join(sorted(meeting_sample)))
        meeting_stats = list(meeting_collection.aggregate([
            {"$group": {
                "_id": "$meeting_status",
                "count": {"$sum": 1},
                "withDeal": {"$sum": {"$cond": [{"$ne": ["$deal_id", None]}, 1, 0]}},
                "withComplete": {"$sum": {"$cond": [{"$ne": ["$meeting_complete_date", None]}, 1, 0]}},
            }},
            {"$sort": {"count": -1}},
        ], maxTimeMS=120000))
        print("Meeting statuses: " + repr(meeting_stats))
        call_collection = reader.collection("mongo_calls")
        print("November call rows: " + str(call_collection.count_documents({
            "call_date": {"$gte": start, "$lt": end},
        })))
        call_rows = list(call_collection.aggregate(
            build_mongo_target_after_meeting_pipeline(start, end),
            allowDiskUse=False, maxTimeMS=120000,
        ))
        meeting_docs = list(meeting_collection.find(
            {"meeting_status": {"$in": ["Проведена", "Прошла успешно"]},
             "deal_id": {"$nin": [None, ""]},
             "meeting_complete_date": {"$ne": None}},
            {"_id": 0, "deal_id": 1, "meeting_complete_date": 1},
            max_time_ms=120000,
        ))
        entries = calculate_target_after_meeting_entries(call_rows, meeting_docs, "Asia/Yekaterinburg")
        print("Eligible target calls with deal: " + str(len(call_rows)))
        print("Eligible target seconds: " + str(sum(row["durationSeconds"] for row in call_rows)))
        print("Successful meeting records: " + str(len(meeting_docs)))
        print("Matched after-meeting seconds: " + str(sum(item.seconds for item in entries)))
        print("Matched after-meeting managers: " + repr(sorted({item.mop_name for item in entries})))
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
