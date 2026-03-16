from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pymongo import MongoClient
import datetime
import joblib
import pandas as pd
from feature_extractor import extract_session_features

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# MongoDB Connection
# -------------------------
client = MongoClient("mongodb://localhost:27017/")
db = client["bot_tracking"]
collection = db["sessions"]

# -------------------------
# Load trained model once
# -------------------------
model = joblib.load("model.pkl")

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
    session_id: str
    events: List[Event]

# -------------------------
# Collect + Auto Predict
# -------------------------
@app.post("/collect")
def collect_data(data: SessionData):

    # Store events
    record = {
        "session_id": data.session_id,
        "events": [e.dict() for e in data.events],
        "created_at": datetime.datetime.utcnow()
    }

    collection.insert_one(record)

    # Try extracting features
    features = extract_session_features(data.session_id)

    if not features:
        return {
            "status": "collecting",
            "events_received": len(data.events),
            "message": "Not enough data yet"
        }

    # Convert to DataFrame (IMPORTANT)
    df = pd.DataFrame([features])

    # Align feature order with model
    df = df[model.feature_names_in_]

    prediction = model.predict(df)[0]
    probability = model.predict_proba(df)[0][1]

    # Save prediction result
    db["predictions"].update_one(
        {"session_id": data.session_id},
        {
            "$set": {
                "prediction": int(prediction),
                "bot_probability": float(probability),
                "updated_at": datetime.datetime.utcnow()
            }
        },
        upsert=True
    )

    return {
        "status": "analyzed",
        "session_id": data.session_id,
        "prediction": "BOT" if prediction == 1 else "HUMAN",
        "bot_probability": float(probability)
    }
