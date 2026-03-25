from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pymongo import MongoClient
import datetime
import joblib
import pandas as pd
import os
import time

from feature_extractor import extract_features

app = FastAPI()

# -------------------------
# CORS Configuration
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# MongoDB Connection
# -------------------------
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URL)
db = client["bot_tracking"]
sessions_collection = db["sessions"]
predictions_collection = db["predictions"]

# -------------------------
# Load trained model
# -------------------------
try:
    model = joblib.load("model.pkl")
    print("✅ Model loaded successfully")
except Exception as e:
    print(f"⚠️ Warning: Model not found or failed to load. {e}")
    model = None

# -------------------------
# Must match train_evasive.py FEATURES exactly
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
# Session Buffers & Config
# -------------------------
session_buffers = {}
WINDOW_SIZE = 20
MAX_BUFFER_SIZE = 2000
MIN_EVENTS_CRITICAL = 15
MIN_EVENTS_STANDARD = 50

# -------------------------
# Request Models
# -------------------------
class Event(BaseModel):
    type: str
    x: Optional[int] = None
    y: Optional[int] = None
    scrollY: Optional[int] = None
    keyDelay: Optional[int] = None
    timestamp: int

class SessionData(BaseModel):
    site_id: str
    session_id: str
    events: List[Event]

# -------------------------
# Root
# -------------------------
@app.get("/")
def home():
    return {"message": "Bot Detection API Running"}

# -------------------------
# Collect + Real-Time Predict
# -------------------------
@app.post("/collect")
def collect_data(data: SessionData):
    try:
        # 1. Store raw events in MongoDB
        record = {
            "site_id": data.site_id,
            "session_id": data.session_id,
            "events": [e.dict() for e in data.events],
            "created_at": datetime.datetime.utcnow()
        }
        sessions_collection.insert_one(record)

        # 2. Update in-memory buffer
        if data.session_id not in session_buffers:
            session_buffers[data.session_id] = []

        session_buffers[data.session_id].extend([e.dict() for e in data.events])

        # Cap buffer to prevent memory overflow
        if len(session_buffers[data.session_id]) > MAX_BUFFER_SIZE:
            session_buffers[data.session_id] = session_buffers[data.session_id][-MAX_BUFFER_SIZE:]

        # 3. Sliding window — keep only last WINDOW_SIZE seconds
        now = int(time.time() * 1000)
        session_buffers[data.session_id] = [
            e for e in session_buffers[data.session_id]
            if now - e["timestamp"] < WINDOW_SIZE * 1000
        ]

        buffer = session_buffers[data.session_id]
        event_count = len(buffer)

        # 4. Tiered minimum events check
        if event_count < MIN_EVENTS_CRITICAL:
            return {
                "status": "collecting",
                "events_collected": event_count,
                "message": "Waiting for more behavioral data"
            }

        # 5. Extract features from in-memory buffer (NOT MongoDB)
        session_start = buffer[0]["timestamp"]
        features = extract_features(buffer, session_start)

        if not features:
            return {
                "status": "collecting",
                "events_collected": event_count,
                "message": "Not enough computable data yet"
            }

        # 6. Build dataframe with exact model feature order
        df = pd.DataFrame([features])
        for col in MODEL_FEATURES:
            if col not in df.columns:
                df[col] = 0.0
        df = df[MODEL_FEATURES]

        # 7. Predict
        probability = model.predict_proba(df)[0][1]

        # Stricter threshold at low event counts
        threshold = 0.95 if event_count < MIN_EVENTS_STANDARD else 0.75
        prediction = 1 if probability >= threshold else 0
        confidence_tier = "early_warning" if event_count < MIN_EVENTS_STANDARD else "standard"

        # 8. Store prediction with features for debugging
        predictions_collection.update_one(
            {"session_id": data.session_id},
            {
                "$set": {
                    "site_id": data.site_id,
                    "prediction": int(prediction),
                    "bot_probability": float(probability),
                    "confidence_tier": confidence_tier,
                    "event_count": event_count,
                    "features": features,
                    "updated_at": datetime.datetime.utcnow()
                }
            },
            upsert=True
        )

        return {
            "status": "analyzed",
            "site_id": data.site_id,
            "session_id": data.session_id,
            "prediction": "BOT" if prediction == 1 else "HUMAN",
            "bot_probability": float(probability),
            "tier": confidence_tier,
            "event_count": event_count
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# -------------------------
# Debug — shows exact features sent to model for any session
# -------------------------
@app.get("/debug/session/{session_id}")
def debug_session(session_id: str):
    buffer = session_buffers.get(session_id)
    if not buffer:
        return {"error": "Session not in buffer — may have expired or not started"}
    session_start = buffer[0]["timestamp"]
    features = extract_features(buffer, session_start)
    return {
        "session_id": session_id,
        "event_count": len(buffer),
        "all_features": features,
        "model_input": {f: round(features.get(f, 0), 4) for f in MODEL_FEATURES}
    }


# -------------------------
# Analytics Endpoints
# -------------------------
@app.get("/analytics/overview")
def overview():
    total_sessions = sessions_collection.count_documents({})
    total_predictions = predictions_collection.count_documents({})
    bots = predictions_collection.count_documents({"prediction": 1})
    humans = predictions_collection.count_documents({"prediction": 0})
    bot_rate = (bots / total_predictions * 100) if total_predictions else 0
    return {
        "total_sessions": total_sessions,
        "total_predictions": total_predictions,
        "bots": bots,
        "humans": humans,
        "bot_rate": bot_rate
    }

@app.get("/analytics/sites")
def site_stats():
    pipeline = [{"$group": {"_id": "$site_id", "sessions": {"$sum": 1}}}]
    return list(sessions_collection.aggregate(pipeline))

@app.get("/analytics/live-sessions")
def live_sessions():
    now = int(time.time() * 1000)
    stale = [sid for sid, evts in session_buffers.items()
             if not evts or now - evts[-1]["timestamp"] > WINDOW_SIZE * 1000]
    for sid in stale:
        del session_buffers[sid]
    active = [{"session_id": k, "event_count": len(v)}
              for k, v in session_buffers.items()]
    return {"active_sessions": len(session_buffers), "sessions": active}

@app.get("/analytics/recent-detections")
def recent():
    data = list(predictions_collection.find({}).sort("updated_at", -1).limit(20))
    for d in data:
        d["_id"] = str(d["_id"])
    return data

@app.get("/analytics/bot-probabilities")
def bot_probabilities():
    pipeline = [
        {
            "$bucket": {
                "groupBy": "$bot_probability",
                "boundaries": [0, 0.2, 0.4, 0.6, 0.8, 1],
                "default": "other",
                "output": {"count": {"$sum": 1}}
            }
        }
    ]
    return list(predictions_collection.aggregate(pipeline))
