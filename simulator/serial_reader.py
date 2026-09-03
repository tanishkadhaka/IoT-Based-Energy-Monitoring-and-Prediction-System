"""
Serial Reader — Captures data from Wokwi ESP32 simulation.

Modes:
  --live      Connect to Wokwi via RFC2217 (port 4001) and capture real serial data
  --demo      Generate simulated JSON readings (same format as the ESP32 sketch)
              for testing the pipeline without Wokwi running

Timestamp Expansion:
  The ESP32 sends 1 reading every 2 seconds. To get enough data for ML training,
  captured readings are replayed across a configurable time span (default 6 months)
  with 15-minute intervals, applying realistic time-of-day and seasonal variations.
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta


# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ROOM_CSV = os.path.join(DATA_DIR, "room_data.csv")

CSV_FIELDS = [
    "timestamp", "room", "device", "power_watts",
    "temperature", "humidity", "is_device_on",
]


def parse_json_line(line: str) -> dict | None:
    """Parse a JSON line from the ESP32 serial output."""
    line = line.strip()
    if not line or not line.startswith("{"):
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def reading_to_rows(data: dict, timestamp: str, room: str = "Room_1") -> list[dict]:
    """
    Convert one ESP32 JSON reading into multiple CSV rows (one per device).
    This matches the format expected by data_processor.py and building_scaler.py.
    """
    temp = data.get("temp", 25.0)
    humidity = data.get("humidity", 50.0)
    rows = []

    # AC
    ac_on = data.get("ac", 0)
    ac_power = 1500.0 if ac_on else 50.0
    rows.append({
        "timestamp": timestamp, "room": room, "device": "AC",
        "power_watts": ac_power, "temperature": temp,
        "humidity": humidity, "is_device_on": ac_on,
    })

    # Heater
    heater_on = data.get("heater", 0)
    heater_power = 2000.0 if heater_on else 10.0
    rows.append({
        "timestamp": timestamp, "room": room, "device": "Heater",
        "power_watts": heater_power, "temperature": temp,
        "humidity": humidity, "is_device_on": heater_on,
    })

    # Fan
    fan_on = data.get("fan", 0)
    fan_power = 75.0 if fan_on else 5.0
    rows.append({
        "timestamp": timestamp, "room": room, "device": "Fan",
        "power_watts": fan_power, "temperature": temp,
        "humidity": humidity, "is_device_on": fan_on,
    })

    # Lights
    light_on = data.get("light", 0)
    light_power = 60.0 if light_on else 2.0
    rows.append({
        "timestamp": timestamp, "room": room, "device": "Lights",
        "power_watts": light_power, "temperature": temp,
        "humidity": humidity, "is_device_on": light_on,
    })

    return rows


# ═════════════════════════════════════════════════════════════════════════════
# LIVE MODE — Connect to Wokwi via RFC2217
# ═════════════════════════════════════════════════════════════════════════════

def run_live(port: int = 4001, max_readings: int = 500):
    """Connect to Wokwi RFC2217 serial and capture live data."""
    try:
        import serial
    except ImportError:
        print("Error: pyserial is required. Install with: pip install pyserial")
        sys.exit(1)

    url = f"rfc2217://localhost:{port}"
    print(f"Connecting to Wokwi at {url}...")
    print(f"Make sure Wokwi simulation is running (F1 -> 'Wokwi: Start Simulator')")
    print(f"Will capture up to {max_readings} readings. Press Ctrl+C to stop early.\n")

    try:
        ser = serial.serial_for_url(url, baudrate=115200, timeout=5)
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Is Wokwi running? Is the simulator tab visible?")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    count = 0

    with open(ROOM_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        try:
            while count < max_readings:
                if ser.in_waiting > 0:
                    raw = ser.readline().decode("utf-8", errors="ignore").strip()
                    if raw:
                        print(f"[DEBUG RAW]: {raw}")
                    
                    data = parse_json_line(raw)
                    if data is None:
                        continue
                    if "error" in data:
                        print(f"  Sensor error: {data['error']}")
                        continue

                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    rows = reading_to_rows(data, now)
                    writer.writerows(rows)
                    f.flush()
                    count += 1

                    power = data.get("power", 0)
                    temp = data.get("temp", 0)
                    print(f"  [{count:4d}] Power: {power:6.0f}W | "
                          f"Temp: {temp:.1f}C | "
                          f"AC:{data.get('ac',0)} Fan:{data.get('fan',0)} "
                          f"Light:{data.get('light',0)} Heater:{data.get('heater',0)}")
                else:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nStopped by user.")
        finally:
            ser.close()

    print(f"\nCaptured {count} readings -> {ROOM_CSV}")
    return count


# ═════════════════════════════════════════════════════════════════════════════
# DEMO MODE — Generate simulated readings (same JSON format as ESP32)
# ═════════════════════════════════════════════════════════════════════════════

def generate_demo_reading(hour: int, month: int) -> dict:
    """Generate a simulated ESP32 reading with realistic patterns."""
    # Temperature: seasonal + diurnal
    monthly_base = {
        1: 18, 2: 20, 3: 25, 4: 30, 5: 35, 6: 34,
        7: 31, 8: 30, 9: 30, 10: 28, 11: 23, 12: 19,
    }
    base_temp = monthly_base.get(month, 28)
    diurnal = 6 * math.sin(math.pi * (hour - 5) / 12) if 5 <= hour <= 17 else -3
    temp = round(base_temp + diurnal + random.uniform(-2, 2), 1)

    # Humidity: monsoon months higher
    if month in (6, 7, 8, 9):
        hum_base = 75
    elif month in (11, 12, 1, 2):
        hum_base = 45
    else:
        hum_base = 55
    humidity = round(hum_base + random.uniform(-10, 10), 1)

    # LDR: low at night (dark -> light on), high during day
    if 6 <= hour <= 18:
        ldr = random.randint(600, 4000)
    else:
        ldr = random.randint(50, 400)

    # Motion: higher during active hours
    if 7 <= hour <= 22:
        motion = 1 if random.random() < 0.65 else 0
    else:
        motion = 1 if random.random() < 0.15 else 0

    # Device states (same logic as sketch.ino)
    ac = 1 if temp > 30 else 0
    heater = 1 if temp < 22 else 0
    light = 1 if ldr < 500 else 0
    fan = motion

    power = 0
    if ac: power += 1500
    if heater: power += 2000
    if fan: power += 75
    if light: power += 60

    return {
        "temp": temp, "humidity": humidity, "ldr": ldr, "motion": motion,
        "ac": ac, "heater": heater, "fan": fan, "light": light,
        "power": power, "current": round(power / 230.0, 2), "voltage": 230.0,
    }


def run_demo(num_readings: int = 500):
    """Generate demo readings mimicking Wokwi output."""
    print(f"Generating {num_readings} demo readings (simulating Wokwi output)...")

    os.makedirs(DATA_DIR, exist_ok=True)
    readings = []

    for i in range(num_readings):
        # Spread across different hours and months for variety
        hour = random.randint(0, 23)
        month = random.randint(1, 12)
        data = generate_demo_reading(hour, month)
        readings.append((data, hour, month))

    with open(ROOM_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for i, (data, hour, month) in enumerate(readings):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = reading_to_rows(data, now)
            writer.writerows(rows)

    print(f"Generated {num_readings} readings -> {ROOM_CSV}")
    return num_readings


# ═════════════════════════════════════════════════════════════════════════════
# EXPAND MODE — Take captured room data and spread across 6 months
# ═════════════════════════════════════════════════════════════════════════════

def expand_timestamps(months: int = 6, interval_minutes: int = 15):
    """
    Take the captured room_data.csv and expand it to cover `months` of data
    at `interval_minutes` intervals. Readings are sampled from the captured pool
    with time-appropriate adjustments applied.
    """
    if not os.path.exists(ROOM_CSV):
        print(f"Error: {ROOM_CSV} not found. Run --live or --demo first.")
        sys.exit(1)

    import pandas as pd
    df = pd.read_csv(ROOM_CSV)
    print(f"Loaded {len(df)} rows from room_data.csv")

    # Group by reading index (every 4 rows = 1 reading for 4 devices)
    readings_count = len(df) // 4
    print(f"  = {readings_count} complete readings")

    # Build time range
    end_date = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=months * 30)
    current = start_date

    total_slots = int((end_date - start_date).total_seconds() / (interval_minutes * 60))
    print(f"Expanding to {months} months ({start_date.date()} -> {end_date.date()})")
    print(f"  Interval: {interval_minutes} min | Target slots: {total_slots}")

    expanded_rows = []
    slot = 0

    while current < end_date:
        hour = current.hour
        month = current.month

        # Pick a base reading from the pool
        base_idx = (slot % readings_count) * 4

        for device_offset in range(4):
            row_idx = base_idx + device_offset
            if row_idx >= len(df):
                row_idx = row_idx % len(df)

            base_row = df.iloc[row_idx].to_dict()

            # Apply time-appropriate adjustments
            temp = float(base_row["temperature"])
            humidity = float(base_row["humidity"])
            power = float(base_row["power_watts"])
            device = base_row["device"]
            is_on = int(base_row["is_device_on"])

            # Seasonal temperature adjustment
            monthly_offset = {
                1: -10, 2: -8, 3: -3, 4: 2, 5: 7, 6: 6,
                7: 3, 8: 2, 9: 2, 10: 0, 11: -5, 12: -9,
            }
            temp += monthly_offset.get(month, 0)

            # Diurnal adjustment
            if 5 <= hour <= 17:
                temp += 4 * math.sin(math.pi * (hour - 5) / 12)
            else:
                temp -= 3

            temp = round(temp + random.uniform(-1.5, 1.5), 1)
            humidity = round(humidity + random.uniform(-8, 8), 1)
            humidity = max(20, min(95, humidity))

            # Re-apply device logic based on adjusted temperature & time
            if device == "AC":
                is_on = 1 if temp > 30 else (1 if temp > 27 and random.random() < 0.4 else 0)
                power = round(1500 * random.uniform(0.85, 1.15), 1) if is_on else 50.0
            elif device == "Heater":
                is_on = 1 if temp < 22 else (1 if temp < 24 and random.random() < 0.3 else 0)
                power = round(2000 * random.uniform(0.9, 1.1), 1) if is_on else 10.0
            elif device == "Fan":
                # Fan usage based on time of day (occupancy proxy)
                if 7 <= hour <= 22:
                    is_on = 1 if random.random() < 0.6 else 0
                else:
                    is_on = 1 if random.random() < 0.15 else 0
                power = round(75 * random.uniform(0.9, 1.1), 1) if is_on else 5.0
            elif device == "Lights":
                # Lights on when dark (night hours)
                if hour < 6 or hour > 18:
                    is_on = 1 if random.random() < 0.8 else 0
                else:
                    is_on = 1 if random.random() < 0.15 else 0
                power = round(60 * random.uniform(0.9, 1.1), 1) if is_on else 2.0

            expanded_rows.append({
                "timestamp": current.strftime("%Y-%m-%d %H:%M:%S"),
                "room": base_row["room"],
                "device": device,
                "power_watts": power,
                "temperature": temp,
                "humidity": humidity,
                "is_device_on": is_on,
            })

        current += timedelta(minutes=interval_minutes)
        slot += 1

        if slot % 5000 == 0:
            pct = (slot / total_slots) * 100
            print(f"  Progress: {pct:.1f}% ({slot}/{total_slots})")

    # Save expanded data back to room_data.csv
    with open(ROOM_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(expanded_rows)

    print(f"\nExpanded {readings_count} readings -> {len(expanded_rows)} rows over {months} months")
    print(f"Saved to {ROOM_CSV}")


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Serial Reader — Capture IoT data from Wokwi ESP32 simulation"
    )
    parser.add_argument("--mode", choices=["live", "demo", "expand"],
                        default="demo",
                        help="live=Wokwi serial, demo=simulated, expand=spread timestamps")
    parser.add_argument("--port", type=int, default=4001,
                        help="RFC2217 port (live mode, default: 4001)")
    parser.add_argument("--readings", type=int, default=500,
                        help="Number of readings to capture/generate")
    parser.add_argument("--months", type=int, default=6,
                        help="Months to expand over (expand mode)")
    parser.add_argument("--interval", type=int, default=15,
                        help="Interval in minutes (expand mode)")
    args = parser.parse_args()

    if args.mode == "live":
        run_live(port=args.port, max_readings=args.readings)
        print("\nNow run: python simulator/serial_reader.py --mode expand")
    elif args.mode == "demo":
        run_demo(num_readings=args.readings)
        print("\nNow run: python simulator/serial_reader.py --mode expand")
    elif args.mode == "expand":
        expand_timestamps(months=args.months, interval_minutes=args.interval)
        print("\nNow run: python simulator/building_scaler.py")


if __name__ == "__main__":
    main()
