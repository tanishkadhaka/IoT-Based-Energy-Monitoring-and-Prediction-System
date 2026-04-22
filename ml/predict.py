"""
Prediction Module
Loads the trained model and makes energy consumption predictions.
"""

import json
import os

import joblib
import numpy as np


class EnergyPredictor:
    """Wrapper for energy consumption prediction."""

    # Electricity rate in INR per kWh
    RATE_PER_KWH = 6.5

    def __init__(self, model_dir: str = None):
        if model_dir is None:
            model_dir = os.path.dirname(os.path.abspath(__file__))

        model_path = os.path.join(model_dir, "model.pkl")
        encoders_path = os.path.join(model_dir, "encoders.pkl")
        metrics_path = os.path.join(model_dir, "model_metrics.json")

        self.model = joblib.load(model_path)
        encoders = joblib.load(encoders_path)
        self.le_room = encoders["room"]
        self.le_device = encoders["device"]

        with open(metrics_path) as f:
            self.metrics = json.load(f)

        print(f"Loaded model: {self.metrics.get('best_model', 'Unknown')}")

    def predict(self, hour: int, day_of_week: int, month: int,
                is_weekend: int, room: str, device: str,
                temperature: float, humidity: float,
                is_device_on: int = 1) -> dict:
        """Predict energy consumption for given parameters."""
        room_enc = self.le_room.transform([room])[0]
        device_enc = self.le_device.transform([device])[0]

        features = np.array([[
            hour, day_of_week, month, is_weekend,
            room_enc, device_enc,
            temperature, humidity, is_device_on,
        ]])

        predicted_kwh = float(self.model.predict(features)[0])
        predicted_kwh = max(0, predicted_kwh)  # No negative energy

        return {
            "predicted_kwh": round(predicted_kwh, 4),
            "estimated_cost_inr": round(predicted_kwh * self.RATE_PER_KWH, 2),
            "room": room,
            "device": device,
            "parameters": {
                "hour": hour, "day_of_week": day_of_week,
                "month": month, "temperature": temperature,
                "humidity": humidity,
            },
        }

    def predict_daily(self, room: str, device: str, month: int,
                      temperature: float, humidity: float) -> dict:
        """Predict total daily energy for a room-device pair."""
        total_kwh = 0

        for hour in range(24):
            day_of_week = 2  # midweek average
            is_weekend = 0
            result = self.predict(
                hour, day_of_week, month, is_weekend,
                room, device, temperature, humidity,
            )
            total_kwh += result["predicted_kwh"]

        return {
            "predicted_daily_kwh": round(total_kwh, 2),
            "estimated_daily_cost_inr": round(total_kwh * self.RATE_PER_KWH, 2),
            "estimated_monthly_kwh": round(total_kwh * 30, 2),
            "estimated_monthly_cost_inr": round(total_kwh * 30 * self.RATE_PER_KWH, 2),
            "room": room,
            "device": device,
        }

    def get_alerts(self, current_power: float, room: str) -> list[dict]:
        """Generate alerts based on power usage."""
        alerts = []

        if current_power > 2000:
            alerts.append({
                "level": "critical",
                "message": f"⚡ High power usage in {room}: {current_power}W",
                "suggestion": "Consider turning off non-essential devices.",
            })
        elif current_power > 1000:
            alerts.append({
                "level": "warning",
                "message": f"⚠ Elevated power in {room}: {current_power}W",
                "suggestion": "AC temperature can be raised by 2°C to save 10% energy.",
            })

        return alerts

    def get_optimization_tips(self) -> list[dict]:
        """Return cost optimization suggestions."""
        return [
            {
                "tip": "Set AC to 24°C instead of 22°C",
                "potential_saving": "~15% on cooling costs",
                "icon": "❄️",
            },
            {
                "tip": "Use LED lights instead of CFL/incandescent",
                "potential_saving": "~75% on lighting costs",
                "icon": "💡",
            },
            {
                "tip": "Switch off devices during non-occupancy hours",
                "potential_saving": "~20% on standby power",
                "icon": "🔌",
            },
            {
                "tip": "Use timer-based scheduling for water heaters",
                "potential_saving": "~30% on heating costs",
                "icon": "⏰",
            },
            {
                "tip": "Shift heavy-load appliances to off-peak hours (10 PM - 6 AM)",
                "potential_saving": "Lower tariff rates in many regions",
                "icon": "📊",
            },
        ]

    def get_model_info(self) -> dict:
        """Return model metadata."""
        return self.metrics
