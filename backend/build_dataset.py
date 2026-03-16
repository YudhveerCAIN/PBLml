import csv
from pymongo import MongoClient
from collections import defaultdict
from feature_extractor import extract_features

MIN_EVENTS = 2

client = MongoClient("mongodb://localhost:27017/")
db = client["bot_tracking"]
collection = db["sessions"]

# Group events by session_id
sessions = defaultdict(list)

for doc in collection.find():
    sessions[doc["session_id"]].extend(doc["events"])

print(f"Total sessions found: {len(sessions)}")

rows = []

for session_id, events in sessions.items():
    print(f"Session {session_id} → {len(events)} events")

    if len(events) < MIN_EVENTS:
        continue

    # 🔥 FIX: normalize timestamps
    for e in events:
        e["timestamp"] = int(e["timestamp"])

    # Sort by time
    events.sort(key=lambda e: e["timestamp"])
    session_start = events[0]["timestamp"]

    features = extract_features(events, session_start)
    if features is None:
        continue

    # TEMP labeling logic
    if features["event_type_entropy"] < 0.8 or features["mouse_event_count"] == 0:
        features["label"] = 1  # bot
    else:
        features["label"] = 0  # human

    rows.append(features)

print(f"Sessions used for dataset: {len(rows)}")

# Save dataset
if rows:
    with open("dataset.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print("dataset.csv generated successfully")
else:
    print("No data written to dataset.csv")
for key in features:
    if features[key] is None or (isinstance(features[key], float) and (features[key] != features[key])):
        features[key] = 0
