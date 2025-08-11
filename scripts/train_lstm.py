"""
scripts/train_lstm.py

Train an LSTM to predict short-term CPU usage from historical cpu_history CSV.

CSV format expected: timestamp, value
Example:
2025-08-11T12:00:00,23.5
2025-08-11T12:00:02,25.1
...
"""

import os
import argparse
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
import pickle

def load_data(csv_path):
    df = pd.read_csv(csv_path, parse_dates=['timestamp'])
    df = df.sort_values('timestamp')
    # Use only the value column
    return df['value'].values.reshape(-1, 1), df['timestamp'].values

def create_sequences(values, window_size):
    X, y = [], []
    for i in range(len(values) - window_size):
        X.append(values[i:i+window_size])
        y.append(values[i+window_size])
    return np.array(X), np.array(y)

def build_model(window_size, dropout=0.2):
    model = Sequential()
    model.add(LSTM(64, input_shape=(window_size, 1), return_sequences=True))
    model.add(Dropout(dropout))
    model.add(LSTM(32, return_sequences=False))
    model.add(Dropout(dropout))
    model.add(Dense(16, activation='relu'))
    model.add(Dense(1, activation='linear'))
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model

def main(args):
    os.makedirs('models', exist_ok=True)

    values, timestamps = load_data(args.csv)
    if len(values) < args.window_size + 2:
        raise SystemExit("Not enough data to train. Collect more samples.")

    scaler = MinMaxScaler(feature_range=(0, 1))
    values_scaled = scaler.fit_transform(values)

    X, y = create_sequences(values_scaled, args.window_size)
    # shuffle split
    split_idx = int(len(X) * (1 - args.val_split))
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    # reshape already correct: (samples, window_size, 1)
    model = build_model(args.window_size, dropout=args.dropout)

    checkpoint_path = os.path.join('models', 'lstm_cpu_best.h5')
    callbacks = [
        EarlyStopping(monitor='val_loss', patience=8, restore_best_weights=True),
        ModelCheckpoint(checkpoint_path, monitor='val_loss', save_best_only=True)
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=callbacks,
        verbose=1
    )

    # final save (weights already best saved)
    model.save(os.path.join('models', 'lstm_cpu.h5'))
    with open(os.path.join('models', 'scaler.pkl'), 'wb') as f:
        pickle.dump(scaler, f)

    print("Training complete. Model saved to models/lstm_cpu.h5 and scaler to models/scaler.pkl")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train LSTM for CPU prediction")
    parser.add_argument('--csv', default='data/cpu_history.csv', help='Path to cpu history CSV')
    parser.add_argument('--window_size', type=int, default=30, help='Number of previous samples used for prediction')
    parser.add_argument('--epochs', type=int, default=60)
    parser.add_argument('--batch_size', type=int, default=32)
    parser.add_argument('--val_split', type=float, default=0.1)
    parser.add_argument('--dropout', type=float, default=0.2)
    args = parser.parse_args()
    main(args)
