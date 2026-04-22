"""
Building Scaler
Takes single-room data (room_data.csv) and scales it to a 5-room building.

Each room applies realistic offsets to temperature, humidity, and device behavior
so the building data looks natural while being grounded in the Wokwi simulation.

Room Profiles:
  Living Room  → Base data from Wokwi (as-is, with small noise)
  Bedroom      → Cooler (-2°C), less fan usage, more night AC
  Kitchen      → Warmer (+3°C), heater at meal times, more lights
  Office       → Stable AC, weekday-heavy, consistent lighting
  Bathroom     → Short heater bursts, minimal fan/AC, low power
"""

import csv
import math
import os
import random
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ROOM_CSV = os.path.join(DATA_DIR, "room_data.csv")
OUTPUT_CSV = os.path.join(DATA_DIR, "raw_sensor_data.csv")

CSV_FIELDS = [
    "timestamp", "room", "device", "power_watts",
    "temperature", "humidity", "is_device_on",
]

# ── Room Profiles ────────────────────────────────────────────────────────────
# Each profile defines offsets and behavioral adjustments relative to base data.

ROOM_PROFILES = {
    "Living Room": {
        "temp_offset": 0,
        "humidity_offset": 0,
        "devices": ["AC", "Fan", "Lights"],  # No heater in living room
        "device_adjustments": {
            "AC":     {"power_mult": 1.0,  "on_boost": 0.0},
            "Fan":    {"power_mult": 1.0,  "on_boost": 0.0},
            "Lights": {"power_mult": 1.0,  "on_boost": 0.0},
        },
    },
    "Bedroom": {
        "temp_offset": -2,
        "humidity_offset": 3,
        "devices": ["AC", "Fan", "Lights"],
        "device_adjustments": {
            "AC":     {"power_mult": 0.9,  "on_boost": 0.1},   # More AC at night
            "Fan":    {"power_mult": 1.0,  "on_boost": -0.15}, # Less fan
            "Lights": {"power_mult": 0.8,  "on_boost": -0.1},  # Dimmer lights
        },
    },
    "Kitchen": {
        "temp_offset": 3,
        "humidity_offset": 8,
        "devices": ["Lights", "Heater"],  # Kitchen has heater (stove proxy), lights
        "device_adjustments": {
            "Lights": {"power_mult": 1.2,  "on_boost": 0.15},
            "Heater": {"power_mult": 1.0,  "on_boost": 0.0},
        },
    },
    "Office": {
        "temp_offset": 0,
        "humidity_offset": -5,
        "devices": ["AC", "Fan", "Lights"],
        "device_adjustments": {
            "AC":     {"power_mult": 1.05, "on_boost": 0.05},
            "Fan":    {"power_mult": 1.0,  "on_boost": 0.1},
            "Lights": {"power_mult": 1.3,  "on_boost": 0.2},   # More lights in office
        },
    },
    "Bathroom": {
        "temp_offset": 1,
        "humidity_offset": 15,
        "devices": ["Lights", "Heater"],  # Bathroom has heater (water heater), lights
        "device_adjustments": {
            "Lights": {"power_mult": 0.7,  "on_boost": 0.0},
            "Heater": {"power_mult": 0.8,  "on_boost": -0.1},  # Shorter bursts
        },
    },
}


def should_device_be_on(base_is_on: int, hour: int, device: str,
                        room_name: str, adj: dict) -> int:
    """Determine if a device should be on with room-specific logic."""
    boost = adj.get("on_boost", 0)

    # Time-based overrides per room
    if room_name == "Kitchen" and device == "Heater":
        # Kitchen heater (cooking): meal times 7-9, 12-14, 18-21
        if 7 <= hour <= 9 or 12 <= hour <= 14 or 18 <= hour <= 21:
            return 1 if random.random() < 0.55 else 0
        else:
            return 1 if random.random() < 0.05 else 0

    if room_name == "Bathroom" and device == "Heater":
        # Water heater: morning 6-9 & evening 18-21
        if 6 <= hour <= 9 or 18 <= hour <= 21:
            return 1 if random.random() < 0.5 else 0
        else:
            return 1 if random.random() < 0.03 else 0

    if room_name == "Bedroom":
        # Bedroom AC more likely at night
        if device == "AC" and (hour >= 22 or hour <= 6):
            boost += 0.2

    if room_name == "Office":
        # Office devices mostly on during work hours
        if 9 <= hour <= 18:
            boost += 0.15
        else:
            boost -= 0.3

    # Apply probability
    base_prob = 0.7 if base_is_on else 0.2
    final_prob = max(0, min(1, base_prob + boost))
    return 1 if random.random() < final_prob else 0


def scale_to_building():
    """Scale room_data.csv to 5 rooms, output raw_sensor_data.csv."""
    if not os.path.exists(ROOM_CSV):
        print(f"Error: {ROOM_CSV} not found.")
        print("Run serial_reader.py first (--mode demo or --mode live)")
        sys.exit(1)

    # Read source data
    with open(ROOM_CSV, "r") as f:
        reader = csv.DictReader(f)
        source_rows = list(reader)

    print(f"Loaded {len(source_rows)} source rows from room_data.csv")

    # Group source rows by timestamp (each timestamp has ~4 device rows)
    timestamps = {}
    for row in source_rows:
        ts = row["timestamp"]
        if ts not in timestamps:
            timestamps[ts] = []
        timestamps[ts].append(row)

    ts_keys = sorted(timestamps.keys())
    print(f"  = {len(ts_keys)} unique timestamps")

    # Generate building data
    building_rows = []
    total = len(ts_keys) * len(ROOM_PROFILES)
    count = 0

    for ts in ts_keys:
        base_devices = timestamps[ts]

        # Parse hour from timestamp
        try:
            hour = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").hour
        except ValueError:
            hour = 12

        for room_name, profile in ROOM_PROFILES.items():
            temp_offset = profile["temp_offset"]
            hum_offset = profile["humidity_offset"]
            room_devices = profile["devices"]
            adjustments = profile["device_adjustments"]

            for device_name in room_devices:
                # Find matching base device row
                base = None
                for row in base_devices:
                    if row["device"] == device_name:
                        base = row
                        break

                if base is None:
                    # If this device doesn't exist in base (e.g., Kitchen needs Heater
                    # but base might not have it ON), find any base row for temp/humidity
                    base = base_devices[0] if base_devices else None
                    if base is None:
                        continue

                # Apply offsets
                temp = float(base["temperature"]) + temp_offset + random.uniform(-1, 1)
                humidity = float(base["humidity"]) + hum_offset + random.uniform(-3, 3)
                humidity = max(20, min(95, humidity))

                adj = adjustments.get(device_name, {})
                base_on = int(base.get("is_device_on", 0))
                is_on = should_device_be_on(base_on, hour, device_name, room_name, adj)

                # Power calculation
                power_mult = adj.get("power_mult", 1.0)
                if is_on:
                    base_watts = {"AC": 1500, "Fan": 75, "Lights": 60, "Heater": 2000}
                    power = base_watts.get(device_name, 100) * power_mult
                    power *= random.uniform(0.85, 1.15)  # noise
                else:
                    standby = {"AC": 50, "Fan": 5, "Lights": 2, "Heater": 10}
                    power = standby.get(device_name, 5)

                building_rows.append({
                    "timestamp": ts,
                    "room": room_name,
                    "device": device_name,
                    "power_watts": round(power, 1),
                    "temperature": round(temp, 1),
                    "humidity": round(humidity, 1),
                    "is_device_on": is_on,
                })

            count += 1
            if count % 10000 == 0:
                pct = (count / total) * 100
                print(f"  Progress: {pct:.1f}%")

    # Save
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(building_rows)

    print(f"\nScaled to {len(ROOM_PROFILES)} rooms: {len(building_rows)} total rows")
    print(f"Saved to {OUTPUT_CSV}")
    print(f"\nNext steps:")
    print(f"  python data/data_processor.py")
    print(f"  python ml/train_model.py")
    print(f"  python backend/app.py")


if __name__ == "__main__":
    scale_to_building()
