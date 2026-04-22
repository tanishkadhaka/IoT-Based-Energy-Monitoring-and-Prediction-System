"""
Data Processor
Converts raw IoT sensor data into processed features for ML training.
Computes kWh, aggregations, and time-based features.
"""

import os
import sys
import pandas as pd
import numpy as np


def load_raw_data(filepath: str) -> pd.DataFrame:
    """Load raw sensor CSV data."""
    print(f"Loading raw data from {filepath}...")
    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    print(f"  Loaded {len(df)} rows, columns: {list(df.columns)}")
    return df


def engineer_features(df: pd.DataFrame, interval_minutes: int = 15) -> pd.DataFrame:
    """Add time-based and energy features."""
    print("Engineering features...")

    # Time features
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["day"] = df["timestamp"].dt.day
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["date"] = df["timestamp"].dt.date

    # Energy calculation: kWh = watts * hours / 1000
    duration_hours = interval_minutes / 60.0
    df["energy_kwh"] = (df["power_watts"] * duration_hours) / 1000.0
    df["energy_kwh"] = df["energy_kwh"].round(4)

    # Time period labels
    def get_time_period(hour):
        if 6 <= hour < 12:
            return "Morning"
        elif 12 <= hour < 17:
            return "Afternoon"
        elif 17 <= hour < 22:
            return "Evening"
        else:
            return "Night"

    df["time_period"] = df["hour"].apply(get_time_period)

    # Encode room and device as numeric
    df["room_encoded"] = df["room"].astype("category").cat.codes
    df["device_encoded"] = df["device"].astype("category").cat.codes

    print(f"  Added features. Shape: {df.shape}")
    return df


def compute_daily_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """Compute daily energy totals per room and device."""
    print("Computing daily aggregates...")
    daily = df.groupby(["date", "room", "device"]).agg(
        total_kwh=("energy_kwh", "sum"),
        avg_power=("power_watts", "mean"),
        max_power=("power_watts", "max"),
        avg_temperature=("temperature", "mean"),
        avg_humidity=("humidity", "mean"),
        active_readings=("is_device_on", "sum"),
        total_readings=("is_device_on", "count"),
    ).reset_index()

    daily["usage_rate"] = (daily["active_readings"] / daily["total_readings"]).round(3)
    print(f"  Daily aggregates: {len(daily)} rows")
    return daily


def compute_monthly_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly energy totals."""
    print("Computing monthly aggregates...")
    df_copy = df.copy()
    df_copy["year_month"] = df_copy["timestamp"].dt.to_period("M").astype(str)

    monthly = df_copy.groupby(["year_month", "room"]).agg(
        total_kwh=("energy_kwh", "sum"),
        avg_daily_kwh=("energy_kwh", "mean"),
        avg_temperature=("temperature", "mean"),
        peak_power=("power_watts", "max"),
    ).reset_index()

    monthly["total_kwh"] = monthly["total_kwh"].round(2)
    monthly["avg_daily_kwh"] = monthly["avg_daily_kwh"].round(4)
    print(f"  Monthly aggregates: {len(monthly)} rows")
    return monthly


def compute_hourly_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Compute average hourly energy profile."""
    print("Computing hourly profile...")
    hourly = df.groupby(["hour", "room"]).agg(
        avg_kwh=("energy_kwh", "mean"),
        avg_power=("power_watts", "mean"),
    ).reset_index()
    hourly["avg_kwh"] = hourly["avg_kwh"].round(4)
    hourly["avg_power"] = hourly["avg_power"].round(1)
    return hourly


def save_processed(df: pd.DataFrame, daily: pd.DataFrame, monthly: pd.DataFrame,
                   hourly: pd.DataFrame, output_dir: str):
    """Save all processed data files."""
    os.makedirs(output_dir, exist_ok=True)

    paths = {
        "processed_data.csv": df,
        "daily_aggregates.csv": daily,
        "monthly_aggregates.csv": monthly,
        "hourly_profile.csv": hourly,
    }

    for filename, data in paths.items():
        path = os.path.join(output_dir, filename)
        data.to_csv(path, index=False)
        print(f"  Saved {filename} ({len(data)} rows)")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_path = os.path.join(base_dir, "raw_sensor_data.csv")

    if not os.path.exists(raw_path):
        print(f"Error: Raw data not found at {raw_path}")
        print("Run the IoT simulator first: python simulator/iot_simulator.py --mode batch")
        sys.exit(1)

    df = load_raw_data(raw_path)
    df = engineer_features(df, interval_minutes=15)
    daily = compute_daily_aggregates(df)
    monthly = compute_monthly_aggregates(df)
    hourly = compute_hourly_profile(df)

    save_processed(df, daily, monthly, hourly, base_dir)

    # Print summary stats
    print("\n" + "=" * 50)
    print("DATA PROCESSING SUMMARY")
    print("=" * 50)
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Total readings: {len(df)}")
    print(f"Total energy: {df['energy_kwh'].sum():.2f} kWh")
    print(f"Rooms: {df['room'].nunique()}")
    print(f"Devices: {df['device'].nunique()}")
    print(f"Features: {list(df.columns)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
