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

    def predict_daily(self, day_of_week: int, month: int,
                      is_weekend: int, room: str, device: str,
                      avg_temperature: float, avg_humidity: float,
                      usage_rate: float = 0.5) -> dict:
        """Predict total daily energy for given parameters."""
        room_enc = self.le_room.transform([room])[0]
        device_enc = self.le_device.transform([device])[0]

        features = np.array([[
            month, day_of_week, is_weekend,
            room_enc, device_enc,
            avg_temperature, avg_humidity, usage_rate,
        ]])

        predicted_kwh = float(self.model.predict(features)[0])
        predicted_kwh = max(0, predicted_kwh)  # No negative energy

        # Import calculate_slab_cost from backend.app (or implement it here)
        # To avoid circular imports, let's implement the slab logic here too or calculate a rough rate.
        # Wait, calculate_slab_cost needs total monthly consumption. 
        # For a single prediction, we can just estimate cost by slab 1 (₹3) or something,
        # but let's implement a static method or assume ₹6.5 for single predictions for now, 
        # or implement the slab cost for a 30-day projection.
        estimated_monthly_kwh = predicted_kwh * 30.0
        
        # Calculate slab cost for the whole month
        monthly_cost = 0.0
        if estimated_monthly_kwh <= 100:
            monthly_cost = estimated_monthly_kwh * 3.0
        elif estimated_monthly_kwh <= 200:
            monthly_cost = (100 * 3.0) + ((estimated_monthly_kwh - 100) * 5.0)
        elif estimated_monthly_kwh <= 400:
            monthly_cost = (100 * 3.0) + (100 * 5.0) + ((estimated_monthly_kwh - 200) * 6.5)
        else:
            monthly_cost = (100 * 3.0) + (100 * 5.0) + (200 * 6.5) + ((estimated_monthly_kwh - 400) * 8.0)
        monthly_cost += 150.0  # Fixed charge

        # Daily cost is monthly / 30
        daily_cost = monthly_cost / 30.0

        return {
            "predicted_daily_kwh": round(predicted_kwh, 4),
            "estimated_daily_cost_inr": round(daily_cost, 2),
            "estimated_monthly_kwh": round(estimated_monthly_kwh, 2),
            "estimated_monthly_cost_inr": round(monthly_cost, 2),
            "room": room,
            "device": device,
            "parameters": {
                "day_of_week": day_of_week, "month": month,
                "avg_temperature": avg_temperature, "avg_humidity": avg_humidity,
                "usage_rate": usage_rate,
            },
        }

    # predict_daily already handles this, remove the old wrapper

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
