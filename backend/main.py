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

from feature_extractor import extract_session_features

app = FastAPI()

# -------------------------
# CORS Configuration
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "*"
    ],
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
model = joblib.load("model.pkl")

print("✅ Model loaded successfully")

# -------------------------
# Session buffers for real-time detection
# -------------------------
session_buffers = {}

WINDOW_SIZE = 5  # seconds

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
# Root endpoint
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

        # -------------------------
        # Store raw events
        # -------------------------
        record = {
            "site_id": data.site_id,
            "session_id": data.session_id,
            "events": [e.dict() for e in data.events],
            "created_at": datetime.datetime.utcnow()
        }

        sessions_collection.insert_one(record)

        # -------------------------
        # Update real-time buffer
        # -------------------------
        if data.session_id not in session_buffers:
            session_buffers[data.session_id] = []

        session_buffers[data.session_id].extend([e.dict() for e in data.events])

        # -------------------------
        # Sliding window filter
        # -------------------------
        now = int(time.time() * 1000)

        session_buffers[data.session_id] = [
            e for e in session_buffers[data.session_id]
            if now - e["timestamp"] < WINDOW_SIZE * 1000
        ]

        # -------------------------
        # Extract features
        # -------------------------
        features = extract_session_features(data.session_id)

        if not features:
            return {
                "status": "collecting",
                "events_received": len(data.events),
                "message": "Not enough data yet"
            }

        # -------------------------
        # Prepare dataframe
        # -------------------------
        df = pd.DataFrame([features])

        df = df[model.feature_names_in_]

        # -------------------------
        # Model prediction
        # -------------------------
        probability = model.predict_proba(df)[0][1]

        threshold = 0.75

        prediction = 1 if probability >= threshold else 0

        # -------------------------
        # Store prediction
        # -------------------------
        predictions_collection.update_one(
            {"session_id": data.session_id},
            {
                "$set": {
                    "site_id": data.site_id,
                    "prediction": int(prediction),
                    "bot_probability": float(probability),
                    "updated_at": datetime.datetime.utcnow()
                }
            },
            upsert=True
        )

        # -------------------------
        # Return result
        # -------------------------
        return {
            "status": "analyzed",
            "site_id": data.site_id,
            "session_id": data.session_id,
            "prediction": "BOT" if prediction == 1 else "HUMAN",
            "bot_probability": float(probability)
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }
    

#analytics endpoint
    
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

    pipeline = [
        {
            "$group": {
                "_id": "$site_id",
                "sessions": {"$sum": 1}
            }
        }
    ]

    sites = list(sessions_collection.aggregate(pipeline))

    return sites

@app.get("/analytics/live-sessions")
def live_sessions():

    active = []

    for session_id, events in session_buffers.items():

        active.append({
            "session_id": session_id,
            "event_count": len(events)
        })

    return {
        "active_sessions": len(session_buffers),
        "sessions": active
    }

@app.get("/analytics/recent-detections")
def recent():

    data = list(
        predictions_collection
        .find({})
        .sort("updated_at",-1)
        .limit(20)
    )

    for d in data:
        d["_id"] = str(d["_id"])

    return data

@app.get("/analytics/bot-probabilities")
def bot_probabilities():

    pipeline = [
        {
            "$bucket": {
                "groupBy": "$bot_probability",
                "boundaries": [0,0.2,0.4,0.6,0.8,1],
                "default": "other",
                "output": {
                    "count": {"$sum":1}
                }
            }
        }
    ]

    result = list(predictions_collection.aggregate(pipeline))

    return result