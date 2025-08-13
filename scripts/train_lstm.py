import os
import joblib
import numpy as np
import psutil
import tensorflow as tf
from collections import deque

# ----------- SETTINGS ------------
SEQ_LENGTH = 10  # number of past readings to use for prediction
MODEL_PATH = "cpu_lstm.h5"
SCALER_PATH = "cpu_scaler.pkl"

# Store recent CPU usage readings
cpu_history = deque(maxlen=SEQ_LENGTH)

# ----------- LOAD MODEL & SCALER -----------
try:
    if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
        model = tf.keras.models.load_model(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        print("✅ LSTM model & scaler loaded")
    else:
        model, scaler = None, None
        print("⚠️ Model or scaler file missing!")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    model, scaler = None, None

# ----------- UPDATE HISTORY & PREDICT -----------
def update_cpu_history():
    """Collects the latest CPU usage reading and adds to history."""
    usage = psutil.cpu_percent(interval=None)  # instant reading
    cpu_history.append(usage)
    return usage

def predict_next_cpu():
    """Predicts the next CPU usage based on history."""
    if len(cpu_history) < SEQ_LENGTH:
        return None  # not enough data yet
    if model is None or scaler is None:
        return None

    seq = np.array(cpu_history).reshape(-1, 1)
    scaled = scaler.transform(seq)
    X = scaled.reshape((1, SEQ_LENGTH, 1))

    pred_scaled = model.predict(X, verbose=0)[0][0]
    predicted_value = scaler.inverse_transform([[pred_scaled]])[0][0]
    return round(float(predicted_value), 2)
