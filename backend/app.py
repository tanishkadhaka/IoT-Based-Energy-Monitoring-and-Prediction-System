"""
Flask Backend
Serves API endpoints for IoT data collection, prediction, and analytics.
Also serves the frontend dashboard.
"""

import csv
import json
import os
import sys

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Add parent dir to path so we can import ml module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__, static_folder=None)
CORS(app)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ML_DIR = os.path.join(BASE_DIR, "ml")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
RAW_CSV = os.path.join(DATA_DIR, "raw_sensor_data.csv")

# ── Load ML model (lazy) ────────────────────────────────────────────────────
predictor = None

def calculate_slab_cost(kwh: float) -> float:
    """Calculate cost based on Indian electricity slab tariff."""
    if kwh <= 200:
        return kwh * 4.0
    elif kwh <= 400:
        return 200 * 4.0 + (kwh - 200) * 6.0
    else:
        return 200 * 4.0 + 200 * 6.0 + (kwh - 400) * 8.0


def get_predictor():
    global predictor
    if predictor is None:
        try:
            from ml.predict import EnergyPredictor
            predictor = EnergyPredictor(ML_DIR)
        except Exception as e:
            print(f"Warning: Could not load model: {e}")
    return predictor


# ── Frontend Serving ─────────────────────────────────────────────────────────

@app.route("/")
def serve_dashboard():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/frontend/<path:filename>")
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ── API: Data Ingestion ─────────────────────────────────────────────────────

@app.route("/api/data", methods=["POST"])
def receive_data():
    """Receive IoT sensor data and append to CSV."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    required_fields = ["room", "device", "power_watts", "temperature", "humidity", "timestamp"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    # Ensure CSV exists with header
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.exists(RAW_CSV)

    fieldnames = ["timestamp", "room", "device", "power_watts", "temperature",
                  "humidity", "is_device_on"]

    with open(RAW_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        row = {k: data.get(k, "") for k in fieldnames}
        writer.writerow(row)

    return jsonify({"status": "ok", "message": "Data received"}), 201


@app.route("/api/data", methods=["GET"])
def get_data():
    """Return sensor data with optional filters."""
    if not os.path.exists(RAW_CSV):
        return jsonify({"data": [], "count": 0})

    df = pd.read_csv(RAW_CSV)

    # Filters
    room = request.args.get("room")
    device = request.args.get("device")
    limit = request.args.get("limit", 500, type=int)

    if room:
        df = df[df["room"] == room]
    if device:
        df = df[df["device"] == device]

    # Return most recent data
    df = df.tail(limit)

    return jsonify({
        "data": df.to_dict(orient="records"),
        "count": len(df),
        "total_rows": len(pd.read_csv(RAW_CSV)),
    })


# ── API: Analytics ───────────────────────────────────────────────────────────

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    """Return aggregated analytics data for the dashboard."""
    result = {
        "daily": [],
        "room_totals": [],
        "device_totals": [],
        "hourly_profile": [],
        "monthly": [],
        "summary": {},
    }

    # Daily aggregates
    daily_path = os.path.join(DATA_DIR, "daily_aggregates.csv")
    if os.path.exists(daily_path):
        daily = pd.read_csv(daily_path)
        # Daily totals across all rooms
        daily_totals = daily.groupby("date").agg(
            total_kwh=("total_kwh", "sum")
        ).reset_index()
        # Last 60 days
        daily_totals = daily_totals.tail(60)
        result["daily"] = daily_totals.to_dict(orient="records")

        # Room totals
        room_totals = daily.groupby("room").agg(
            total_kwh=("total_kwh", "sum")
        ).reset_index()
        result["room_totals"] = room_totals.to_dict(orient="records")

        # Device totals
        device_totals = daily.groupby("device").agg(
            total_kwh=("total_kwh", "sum")
        ).reset_index()
        result["device_totals"] = device_totals.to_dict(orient="records")

    # Hourly profile
    hourly_path = os.path.join(DATA_DIR, "hourly_profile.csv")
    if os.path.exists(hourly_path):
        hourly = pd.read_csv(hourly_path)
        hourly_agg = hourly.groupby("hour").agg(
            avg_power=("avg_power", "mean")
        ).reset_index()
        result["hourly_profile"] = hourly_agg.to_dict(orient="records")

    # Monthly
    monthly_path = os.path.join(DATA_DIR, "monthly_aggregates.csv")
    if os.path.exists(monthly_path):
        monthly = pd.read_csv(monthly_path)
        monthly_agg = monthly.groupby("year_month").agg(
            total_kwh=("total_kwh", "sum")
        ).reset_index()
        result["monthly"] = monthly_agg.to_dict(orient="records")

    # Summary stats
    processed_path = os.path.join(DATA_DIR, "processed_data.csv")
    if os.path.exists(processed_path):
        proc = pd.read_csv(processed_path)
        result["summary"] = {
            "total_readings": len(proc),
            "total_kwh": round(proc["energy_kwh"].sum(), 2),
            "avg_power": round(proc["power_watts"].mean(), 1),
            "peak_power": round(proc["power_watts"].max(), 1),
            "rooms": int(proc["room"].nunique()),
            "devices": int(proc["device"].nunique()),
            "date_range_start": str(proc["timestamp"].min()[:10]) if "timestamp" in proc.columns else "",
            "date_range_end": str(proc["timestamp"].max()[:10]) if "timestamp" in proc.columns else "",
            "total_cost_inr": round(calculate_slab_cost(proc["energy_kwh"].sum()), 2),
        }

    return jsonify(result)


# ── API: Prediction ──────────────────────────────────────────────────────────

@app.route("/api/predict", methods=["POST"])
def predict():
    """Predict energy consumption for given parameters."""
    pred = get_predictor()
    if pred is None:
        return jsonify({"error": "Model not loaded. Train the model first."}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    try:
        result = pred.predict_daily(
            day_of_week=int(data.get("day_of_week", 2)),
            month=int(data.get("month", 6)),
            is_weekend=int(data.get("is_weekend", 0)),
            room=data.get("room", "Living Room"),
            device=data.get("device", "AC"),
            avg_temperature=float(data.get("temperature", 30)),
            avg_humidity=float(data.get("humidity", 60)),
            usage_rate=float(data.get("usage_rate", 0.5)),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/predict/daily", methods=["POST"])
def predict_daily():
    """Predict daily energy consumption."""
    pred = get_predictor()
    if pred is None:
        return jsonify({"error": "Model not loaded"}), 503

    data = request.get_json()
    try:
        result = pred.predict_daily(
            day_of_week=2,  # default mid-week
            month=int(data.get("month", 6)),
            is_weekend=0,
            room=data.get("room", "Living Room"),
            device=data.get("device", "AC"),
            avg_temperature=float(data.get("temperature", 30)),
            avg_humidity=float(data.get("humidity", 60)),
            usage_rate=0.5, # default
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── API: Model Info ──────────────────────────────────────────────────────────

@app.route("/api/model-info", methods=["GET"])
def model_info():
    """Return model metrics and feature importances."""
    metrics_path = os.path.join(ML_DIR, "model_metrics.json")
    results_path = os.path.join(ML_DIR, "training_results.csv")

    result = {}

    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            result["metrics"] = json.load(f)

    if os.path.exists(results_path):
        df = pd.read_csv(results_path)
        result["training_results"] = df.to_dict(orient="records")

    return jsonify(result)


# ── API: Alerts ──────────────────────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
def alerts():
    """Return alerts and optimization tips."""
    pred = get_predictor()
    tips = pred.get_optimization_tips() if pred else []

    # Generate alerts from recent data
    alerts_list = []
    if os.path.exists(RAW_CSV):
        df = pd.read_csv(RAW_CSV)
        recent = df.tail(100)

        # Check for high power rooms
        room_power = recent.groupby("room")["power_watts"].mean()
        for room, avg_power in room_power.items():
            if avg_power > 1500:
                alerts_list.append({
                    "level": "critical",
                    "message": f"⚡ High average power in {room}: {avg_power:.0f}W",
                    "suggestion": "Consider reducing AC usage or turning off idle devices.",
                })
            elif avg_power > 800:
                alerts_list.append({
                    "level": "warning",
                    "message": f"⚠ Elevated power in {room}: {avg_power:.0f}W",
                    "suggestion": "Monitor this room for unusual spikes.",
                })

    return jsonify({
        "alerts": alerts_list,
        "tips": tips,
    })


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'=' * 50}")
    print("  Energy Consumption Predictor — Backend")
    print(f"{'=' * 50}")
    print(f"  Data dir:     {DATA_DIR}")
    print(f"  ML dir:       {ML_DIR}")
    print(f"  Frontend dir: {FRONTEND_DIR}")
    print(f"  Dashboard:    http://127.0.0.1:5000")
    print(f"{'=' * 50}\n")

    app.run(debug=True, host="0.0.0.0", port=5000)
