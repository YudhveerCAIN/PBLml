import math
import numpy as np
from collections import Counter
from pymongo import MongoClient
import os


# -------------------------
# MongoDB Connection
# -------------------------
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")

client = MongoClient(MONGO_URL)

db = client["bot_tracking"]

collection = db["sessions"]


# -------------------------
# Entropy Calculation
# -------------------------
def compute_entropy(values):
    if not values:
        return 0

    counts = Counter(values)
    total = len(values)

    entropy = 0
    for c in counts.values():
        p = c / total
        entropy -= p * math.log2(p)

    return entropy


# -------------------------
# Core Feature Extraction
# -------------------------
def extract_features(events, session_start, window_seconds=None):

    now = max(e["timestamp"] for e in events)

    # Filter window if needed
    if window_seconds:
        events = [
            e for e in events
            if e["timestamp"] >= now - window_seconds * 1000
        ]

    if len(events) < 2:
        return None

    mouse_moves = [e for e in events if e["type"] == "mousemove"]
    clicks = [e for e in events if e["type"] == "click"]
    scrolls = [e for e in events if e["type"] == "scroll"]
    keys = [e for e in events if e["type"] == "keydown"]

    # -------------------------
    # Mouse speed
    # -------------------------
    speeds = []

    for i in range(1, len(mouse_moves)):
        dx = mouse_moves[i]["x"] - mouse_moves[i - 1]["x"]
        dy = mouse_moves[i]["y"] - mouse_moves[i - 1]["y"]
        dt = mouse_moves[i]["timestamp"] - mouse_moves[i - 1]["timestamp"]

        if dt > 0:
            speeds.append(math.sqrt(dx * dx + dy * dy) / dt)

    # -------------------------
    # Click intervals
    # -------------------------
    click_intervals = [
        clicks[i]["timestamp"] - clicks[i - 1]["timestamp"]
        for i in range(1, len(clicks))
    ]

    # -------------------------
    # Scroll jumps
    # -------------------------
    scroll_jumps = [
        abs(scrolls[i]["scrollY"] - scrolls[i - 1]["scrollY"])
        for i in range(1, len(scrolls))
    ]

    # -------------------------
    # Key delays
    # -------------------------
    key_delays = [k["keyDelay"] for k in keys if k["keyDelay"]]

    # -------------------------
    # Feature vector
    # -------------------------
    feature_vector = {

        "mouse_event_count": len(mouse_moves),

        "avg_mouse_speed": np.mean(speeds) if speeds else 0,

        "mouse_speed_std": np.std(speeds) if speeds else 0,

        "mouse_direction_entropy": compute_entropy([
            math.atan2(
                mouse_moves[i]["y"] - mouse_moves[i - 1]["y"],
                mouse_moves[i]["x"] - mouse_moves[i - 1]["x"]
            )
            for i in range(1, len(mouse_moves))
        ]),

        "click_count": len(clicks),

        "click_rate": len(clicks) / max(1, (now - session_start) / 1000),

        "click_interval_std": np.std(click_intervals) if click_intervals else 0,

        "scroll_count": len(scrolls),

        "scroll_variance": np.var(scroll_jumps) if scroll_jumps else 0,

        "avg_scroll_jump": np.mean(scroll_jumps) if scroll_jumps else 0,

        "key_event_count": len(keys),

        "avg_key_delay": np.mean(key_delays) if key_delays else 0,

        "key_delay_std": np.std(key_delays) if key_delays else 0,

        "total_events": len(events),

        "event_rate": len(events) / max(1, (now - session_start) / 1000),

        "event_type_entropy": compute_entropy([e["type"] for e in events])

    }

    return feature_vector


# -------------------------
# Extract features for session
# -------------------------
def extract_session_features(session_id, window_seconds=None):

    docs = collection.find({"session_id": session_id})

    all_events = []

    for doc in docs:
        all_events.extend(doc["events"])

    if len(all_events) < 2:
        return None

    # Sort events
    all_events.sort(key=lambda e: e["timestamp"])

    session_start = all_events[0]["timestamp"]

    return extract_features(
        all_events,
        session_start,
        window_seconds=window_seconds
    )


# -------------------------
# Debug Mode
# -------------------------
if __name__ == "__main__":

    latest_doc = collection.find_one(sort=[("_id", -1)])

    if not latest_doc:
        print("No sessions found.")
        exit()

    session_id = latest_doc["session_id"]

    print(f"\nAnalyzing session: {session_id}")

    features = extract_session_features(session_id)

    print("\nExtracted Features:")
    print(features)