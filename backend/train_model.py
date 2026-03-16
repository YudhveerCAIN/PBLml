import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# Load dataset
df = pd.read_csv("new_dataset.csv")

print("Dataset shape:", df.shape)
print("\nLabel distribution:\n", df["label"].value_counts())

# Replace NaN or infinite values
df = df.replace([np.inf, -np.inf], np.nan)
df = df.fillna(0)

# Separate features and labels
# X = df.drop("label", axis=1)
X = df.drop(columns=[
    "label",
    "total_events",
    "mouse_event_count",
    "scroll_count",
    "key_event_count",
    "event_rate"
])

y = df["label"]

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.3,
    random_state=42,
    stratify=y
)

print("\nTraining samples:", len(X_train))
print("Testing samples:", len(X_test))

# Train Random Forest
model = RandomForestClassifier(
    n_estimators=200,
    random_state=42
)

model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)

print("\n=== Accuracy ===")
print(accuracy_score(y_test, y_pred))

print("\n=== Classification Report ===")
print(classification_report(y_test, y_pred))

print("\n=== Confusion Matrix ===")
print(confusion_matrix(y_test, y_pred))

# Feature importance
importance = pd.Series(
    model.feature_importances_,
    index=X.columns
).sort_values(ascending=False)

print("\n=== Feature Importance ===")
print(importance)

# Save model
joblib.dump(model, "model.pkl")
print("\nModel saved as model.pkl")
