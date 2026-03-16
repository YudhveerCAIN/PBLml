import joblib
import numpy as np

# Load trained model once (important)
model = joblib.load("model.pkl")

FEATURE_COLUMNS = [
    "mouse_event_count",
    "avg_mouse_speed",
    "mouse_speed_std",
    "mouse_direction_entropy",
    "click_count",
    "click_rate",
    "click_interval_std",
    "scroll_count",
    "scroll_variance",
    "avg_scroll_jump",
    "key_event_count",
    "avg_key_delay",
    "key_delay_std",
    "total_events",
    "event_rate",
    "event_type_entropy"
]

def predict_session(features_dict):
    # Convert to correct order
    X = np.array([[features_dict[col] for col in FEATURE_COLUMNS]])
    
    prediction = model.predict(X)[0]
    confidence = model.predict_proba(X)[0][prediction]
    
    return {
        "prediction": int(prediction),
        "confidence": float(confidence)
    }
