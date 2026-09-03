"""
IoT Energy Consumption Simulator — FALLBACK MODE

This is the fallback data generator for when Wokwi is not available.
It produces the same CSV format as the Wokwi pipeline (serial_reader → building_scaler).

PRIMARY PIPELINE (with Wokwi):
  1. Start Wokwi simulation (F1 → "Wokwi: Start Simulator")
  2. python simulator/serial_reader.py --mode live     (capture from Wokwi)
  3. python simulator/serial_reader.py --mode expand   (spread over 6 months)
  4. python simulator/building_scaler.py               (scale to 5 rooms)
  5. python data/data_processor.py                     (feature engineering)
  6. python ml/train_model.py                          (train model)
  7. python backend/app.py                             (start dashboard)

FALLBACK (without Wokwi):
  1. python simulator/iot_simulator.py --mode batch    (generate 6 months data directly)
  2. python data/data_processor.py
  3. python ml/train_model.py
  4. python backend/app.py
"""

import argparse
import csv
import json
import math
import os
import random
import time
from datetime import datetime, timedelta

import requests

# ── Device Definitions (watts) ──────────────────────────────────────────────
DEVICES = {
    "AC":     {"base_watts": 1500, "standby_watts": 50},
    "Fan":    {"base_watts": 75,   "standby_watts": 5},
    "Lights": {"base_watts": 60,   "standby_watts": 2},
    "Heater": {"base_watts": 2000, "standby_watts": 10},
}

# ── Room Configurations ─────────────────────────────────────────────────────
ROOMS = {
    "Living Room": ["AC", "Fan", "Lights"],
    "Bedroom":     ["AC", "Fan", "Lights"],
    "Kitchen":     ["Lights", "Heater"],
    "Office":      ["AC", "Fan", "Lights"],
    "Bathroom":    ["Lights", "Heater"],
}

# ── Backend endpoint ────────────────────────────────────────────────────────
API_URL = "http://127.0.0.1:5000/api/data"


def get_outdoor_temperature(hour: int, month: int) -> float:
    """Simulate outdoor temperature based on time of day and month."""
    # Monthly base temperatures (India-like climate)
    monthly_base = {
        1: 18, 2: 20, 3: 25, 4: 30, 5: 35, 6: 34,
        7: 31, 8: 30, 9: 30, 10: 28, 11: 23, 12: 19,
    }
    base = monthly_base.get(month, 28)
    # Diurnal variation: peaks at ~14:00, lowest at ~05:00
    variation = 6 * math.sin(math.pi * (hour - 5) / 12) if 5 <= hour <= 17 else -3
    noise = random.uniform(-2, 2)
    return round(base + variation + noise, 1)


def get_humidity(hour: int, month: int) -> float:
    """Simulate humidity based on time and season."""
    # Monsoon months have higher humidity
    if month in (6, 7, 8, 9):
        base = 75
    elif month in (11, 12, 1, 2):
        base = 45
    else:
        base = 55
    # Higher humidity at night/morning
    time_factor = -10 * math.sin(math.pi * (hour - 6) / 12) if 6 <= hour <= 18 else 8
    noise = random.uniform(-5, 5)
    return round(max(20, min(95, base + time_factor + noise)), 1)


def device_on_probability(device: str, hour: int, is_weekend: bool, temperature: float) -> float:
    """
    Return probability [0, 1] that a device is ON at a given hour.
    Models realistic usage patterns but scaled down for medium-sized Indian homes (~3000 kWh/year).
    """
    if device == "AC":
        temp_factor = max(0, (temperature - 25) / 20)
        if 0 <= hour < 6:
            base = 0.05 if temperature > 28 else 0.02
        elif 6 <= hour < 9:
            base = 0.02
        elif 9 <= hour < 12:
            base = 0.05
        elif 12 <= hour < 16:
            base = 0.15
        elif 16 <= hour < 20:
            base = 0.10
        else:
            base = 0.08
        prob = min(1.0, base + temp_factor * 0.1)
        if is_weekend:
            prob = min(1.0, prob + 0.05)
        return prob

    elif device == "Fan":
        if 0 <= hour < 6:
            return 0.15
        elif 6 <= hour < 9:
            return 0.10
        elif 9 <= hour < 17:
            return 0.08 if not is_weekend else 0.15
        else:
            return 0.12

    elif device == "Lights":
        if 0 <= hour < 6:
            return 0.01
        elif 6 <= hour < 8:
            return 0.05
        elif 8 <= hour < 17:
            return 0.02 if not is_weekend else 0.05
        elif 17 <= hour < 22:
            return 0.25
        else:
            return 0.08

    elif device == "Heater":
        if 6 <= hour < 9:
            return 0.10
        elif 18 <= hour < 21:
            return 0.08
        else:
            return 0.01

    return 0.02


def generate_reading(room: str, device: str, timestamp: datetime, temperature: float, humidity: float) -> dict:
    """Generate a single sensor reading for a room-device pair."""
    hour = timestamp.hour
    is_weekend = timestamp.weekday() >= 5
    prob = device_on_probability(device, hour, is_weekend, temperature)
    is_on = random.random() < prob

    dev_info = DEVICES[device]
    if is_on:
        if device == "AC":
            power = random.randint(1000, 1800)
        elif device == "Fan":
            power = random.randint(60, 100)
        elif device == "Lights":
            power = random.randint(10, 40)
        elif device == "Heater":
            power = random.randint(1500, 2500)
        else:
            variation = random.uniform(0.85, 1.15)
            power = round(dev_info["base_watts"] * variation, 1)
    else:
        power = dev_info["standby_watts"]

    return {
        "room": room,
        "device": device,
        "power_watts": float(power),
        "temperature": temperature,
        "humidity": humidity,
        "is_device_on": int(is_on),
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
    }


def generate_batch_data(months: int = 6, interval_minutes: int = 15) -> list[dict]:
    """Generate historical data for the specified number of months."""
    data = []
    end_date = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=months * 30)
    current = start_date

    total_steps = int((end_date - start_date).total_seconds() / (interval_minutes * 60))
    step = 0

    print(f"Generating {months} months of data ({start_date.date()} to {end_date.date()})...")
    print(f"Interval: {interval_minutes} min | Estimated rows: ~{total_steps * sum(len(v) for v in ROOMS.values())}")

    while current < end_date:
        temp = get_outdoor_temperature(current.hour, current.month)
        humidity = get_humidity(current.hour, current.month)

        for room, devices in ROOMS.items():
            for device in devices:
                reading = generate_reading(room, device, current, temp, humidity)
                data.append(reading)

        current += timedelta(minutes=interval_minutes)
        step += 1
        if step % 2000 == 0:
            pct = (step / total_steps) * 100
            print(f"  Progress: {pct:.1f}% ({step}/{total_steps})")

    print(f"Generated {len(data)} readings.")
    return data


def save_to_csv(data: list[dict], filepath: str):
    """Save readings to CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    fieldnames = ["timestamp", "room", "device", "power_watts", "temperature", "humidity", "is_device_on"]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Saved {len(data)} rows to {filepath}")


def send_to_backend(reading: dict):
    """Send a single reading to the Flask backend."""
    try:
        resp = requests.post(API_URL, json=reading, timeout=5)
        if resp.status_code == 201:
            print(f"  ✓ Sent: {reading['room']}/{reading['device']} = {reading['power_watts']}W")
        else:
            print(f"  ✗ Error {resp.status_code}: {resp.text}")
    except requests.ConnectionError:
        print("  ✗ Backend not reachable. Is Flask running?")


def run_realtime(interval_sec: int = 5):
    """Real-time mode: generate & send data every N seconds."""
    print(f"Starting real-time simulation (interval: {interval_sec}s)")
    print(f"Sending data to {API_URL}")
    print("Press Ctrl+C to stop.\n")

    while True:
        now = datetime.now()
        temp = get_outdoor_temperature(now.hour, now.month)
        humidity = get_humidity(now.hour, now.month)

        # Pick a random room-device pair each tick (simulating sensor rotation)
        room = random.choice(list(ROOMS.keys()))
        device = random.choice(ROOMS[room])
        reading = generate_reading(room, device, now, temp, humidity)

        print(f"[{now.strftime('%H:%M:%S')}] {room}/{device}: {reading['power_watts']}W "
              f"(Temp: {temp}°C, Humidity: {humidity}%)")
        send_to_backend(reading)
        time.sleep(interval_sec)


def main():
    parser = argparse.ArgumentParser(description="IoT Energy Consumption Simulator")
    parser.add_argument("--mode", choices=["batch", "realtime"], default="batch",
                        help="Generation mode (default: batch)")
    parser.add_argument("--months", type=int, default=6,
                        help="Months of historical data to generate (batch mode)")
    parser.add_argument("--interval", type=int, default=15,
                        help="Data interval in minutes (batch) or seconds (realtime)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (batch mode)")
    args = parser.parse_args()

    if args.mode == "batch":
        output_path = args.output or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "raw_sensor_data.csv"
        )
        data = generate_batch_data(months=args.months, interval_minutes=args.interval)
        save_to_csv(data, output_path)
        print("\nBatch generation complete!")
    else:
        run_realtime(interval_sec=args.interval if args.interval < 60 else 5)


if __name__ == "__main__":
    main()
