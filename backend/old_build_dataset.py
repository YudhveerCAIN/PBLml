import csv
from pymongo import MongoClient
from collections import defaultdict
from feature_extractor import extract_features

MIN_EVENTS = 2


client = MongoClient("mongodb://localhost:27017/")
db = client["bot_tracking"]
collection = db["sessions"]

# Group documents by session_id
sessions = defaultdict(list)

for doc in collection.find():
    sessions[doc["session_id"]].extend(doc["events"])

print(f"Total sessions found: {len(sessions)}")

rows = []

for session_id, events in sessions.items():
    print(f"Session {session_id} → {len(events)} events")

    if len(events) < MIN_EVENTS:
        continue

    # Sort events by time
    events.sort(key=lambda e: e["timestamp"])
    session_start = events[0]["timestamp"]

    features = extract_features(events, session_start)
    if not features:
        continue

    # TEMP label (human)
    # Simple labeling rule for now
# Selenium bots have very low key delay variability
if features["key_event_count"] > 0 and features["key_delay_std"] < 20:
    features["label"] = 1  # bot
else:
    features["label"] = 0  # human

    rows.append(features)

print(f"Sessions used for dataset: {len(rows)}")

# Save to CSV
if rows:
    with open("dataset.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

print("dataset.csv generated successfully")
