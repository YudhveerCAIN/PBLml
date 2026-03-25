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
# Must match MODEL_FEATURES in main.py and train_evasive.py
# -------------------------
MODEL_FEATURES = [
    "key_delay_std",
    "scroll_count",
    "avg_key_delay",
    "total_events",
    "mouse_event_count",
    "click_rate",
    "mouse_speed_std",
    "avg_mouse_speed",
    "event_rate",
    "mouse_direction_entropy"
]


# -------------------------
# Entropy Calculation
# -------------------------
def compute_entropy(values):
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    entropy = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


# -------------------------
# Direction entropy using angle bins (matches training)
# -------------------------
def compute_direction_entropy(mouse_moves, n_bins=16):
    if len(mouse_moves) < 2:
        return 0.0
    bins = [0] * n_bins
    for i in range(1, len(mouse_moves)):
        dx = mouse_moves[i]["x"] - mouse_moves[i-1]["x"]
        dy = mouse_moves[i]["y"] - mouse_moves[i-1]["y"]
        if dx == 0 and dy == 0:
            continue
        angle = math.atan2(dy, dx)
        if not math.isfinite(angle):
            continue
        idx = int((angle + math.pi) / (2 * math.pi) * n_bins) % n_bins
        bins[idx] += 1
    return compute_entropy([i for i, c in enumerate(bins) for _ in range(c)])


# -------------------------
# Core Feature Extraction
# Returns exactly MODEL_FEATURES keys
# -------------------------
def extract_features(events, session_start, window_seconds=None):
    if not events:
        return None

    now = max(e["timestamp"] for e in events)

    if window_seconds:
        events = [e for e in events
                  if e["timestamp"] >= now - window_seconds * 1000]

    if len(events) < 2:
        return None

    # Split by type
    mouse_moves = [e for e in events if e["type"] == "mousemove"]
    clicks      = [e for e in events if e["type"] == "click"]
    scrolls     = [e for e in events if e["type"] == "scroll"]
    keys        = [e for e in events if e["type"] == "keydown"]

    session_duration_s = max(1, (now - session_start) / 1000)

    # ── Mouse speed ──
    speeds = []
    for i in range(1, len(mouse_moves)):
        dx = mouse_moves[i]["x"] - mouse_moves[i-1]["x"]
        dy = mouse_moves[i]["y"] - mouse_moves[i-1]["y"]
        dt = mouse_moves[i]["timestamp"] - mouse_moves[i-1]["timestamp"]
        if dt > 0:
            s = math.sqrt(dx*dx + dy*dy) / dt * 1000  # px/s
            if math.isfinite(s):
                speeds.append(s)

    avg_mouse_speed = float(np.mean(speeds)) if speeds else 0.0
    mouse_speed_std = float(np.std(speeds))  if speeds else 0.0

    # ── Mouse direction entropy ──
    mouse_direction_entropy = compute_direction_entropy(mouse_moves)

    # ── Key delays ──
    # Use keyDelay field first; fall back to inter-event timestamps
    key_delays = [k["keyDelay"] for k in keys
                  if k.get("keyDelay") and k["keyDelay"] > 0]
    if not key_delays and len(keys) > 1:
        key_delays = [
            keys[i]["timestamp"] - keys[i-1]["timestamp"]
            for i in range(1, len(keys))
            if keys[i]["timestamp"] - keys[i-1]["timestamp"] > 0
        ]

    avg_key_delay = float(np.mean(key_delays)) if key_delays else 0.0
    key_delay_std = float(np.std(key_delays))  if key_delays else 0.0

    # ── Return exactly MODEL_FEATURES ──
    return {
        "key_delay_std":           round(key_delay_std, 4),
        "scroll_count":            len(scrolls),
        "avg_key_delay":           round(avg_key_delay, 4),
        "total_events":            len(events),
        "mouse_event_count":       len(mouse_moves),
        "click_rate":              round(len(clicks) / session_duration_s, 4),
        "mouse_speed_std":         round(mouse_speed_std, 4),
        "avg_mouse_speed":         round(avg_mouse_speed, 4),
        "event_rate":              round(len(events) / session_duration_s, 4),
        "mouse_direction_entropy": round(mouse_direction_entropy, 4),
    }


# -------------------------
# MongoDB-based extraction (used for offline analysis only)
# main.py uses extract_features() directly with the in-memory buffer
# -------------------------
def extract_session_features(session_id, window_seconds=None):
    docs = list(collection.find({"session_id": session_id}))
    all_events = []
    for doc in docs:
        all_events.extend(doc.get("events", []))
    if len(all_events) < 2:
        return None
    all_events.sort(key=lambda e: e["timestamp"])
    return extract_features(all_events, all_events[0]["timestamp"],
                            window_seconds=window_seconds)


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
    if features:
        print("\nExtracted Features:")
        for k, v in features.items():
            status = "✓" if k in MODEL_FEATURES else "✗ not in model"
            print(f"  {k:<28} {v}  {status}")
    else:
        print("Not enough events.")
