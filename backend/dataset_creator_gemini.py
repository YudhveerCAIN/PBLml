import pandas as pd
import numpy as np
import random

def generate_human():
    mouse_events = random.randint(5, 200)
    scroll_events = random.randint(0, 400)
    key_events = random.randint(0, 100)
    click_count = random.randint(1, 25)

    total_events = mouse_events + scroll_events + key_events + click_count

    return {
        "mouse_event_count": mouse_events,
        "avg_mouse_speed": np.random.normal(0.5, 0.4),
        "mouse_speed_std": np.random.normal(0.6, 0.5),
        "mouse_direction_entropy": np.random.normal(3.0, 1.5),
        "click_count": click_count,
        "click_rate": np.random.normal(1.0, 1.0),
        "click_interval_std": np.random.normal(800, 1000),
        "scroll_count": scroll_events,
        "scroll_variance": np.random.normal(800, 1000),
        "avg_scroll_jump": np.random.normal(40, 30),
        "key_event_count": key_events,
        "avg_key_delay": np.random.normal(250, 150),
        "key_delay_std": np.random.normal(120, 100),
        "total_events": total_events,
        "event_rate": np.random.normal(5, 5),
        "event_type_entropy": np.random.normal(1.5, 0.7),
        "label": 0
    }

def generate_bot():
    mouse_events = random.randint(0, 800)
    scroll_events = random.randint(0, 1200)
    key_events = random.randint(0, 200)
    click_count = random.randint(0, 20)

    total_events = mouse_events + scroll_events + key_events + click_count

    return {
        "mouse_event_count": mouse_events,
        "avg_mouse_speed": np.random.normal(0.8, 0.6),
        "mouse_speed_std": np.random.normal(1.0, 0.7),
        "mouse_direction_entropy": np.random.normal(1.5, 1.2),
        "click_count": click_count,
        "click_rate": np.random.normal(0.8, 1.0),
        "click_interval_std": np.random.normal(500, 800),
        "scroll_count": scroll_events,
        "scroll_variance": np.random.normal(1500, 2000),
        "avg_scroll_jump": np.random.normal(60, 50),
        "key_event_count": key_events,
        "avg_key_delay": np.random.normal(120, 150),
        "key_delay_std": np.random.normal(80, 80),
        "total_events": total_events,
        "event_rate": np.random.normal(10, 10),
        "event_type_entropy": np.random.normal(1.0, 0.8),
        "label": 1
    }

data = []

for _ in range(5000):
    data.append(generate_human())

for _ in range(5000):
    data.append(generate_bot())

df = pd.DataFrame(data)

# Remove negative values
df[df < 0] = 0

# Shuffle
df = df.sample(frac=1).reset_index(drop=True)

df.to_csv("new_dataset.csv", index=False)

print("Dataset generated:", df.shape)
