"""
ML Training Pipeline
Trains Linear Regression and Random Forest models on processed energy data.
Outputs the best model, metrics, and training results.
"""

import json
import os
import sys
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")


def load_data(filepath: str) -> pd.DataFrame:
    """Load processed sensor data."""
    print(f"Loading data from {filepath}...")
    df = pd.read_csv(filepath)
    print(f"  Shape: {df.shape}")
    return df


def prepare_features(df: pd.DataFrame):
    """Prepare feature matrix and target variable."""
    print("Preparing features...")

    # Encode categorical columns
    le_room = LabelEncoder()
    le_device = LabelEncoder()
    df["room_enc"] = le_room.fit_transform(df["room"])
    df["device_enc"] = le_device.fit_transform(df["device"])

    # Extract date features
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    feature_cols = [
        "month", "day_of_week", "is_weekend",
        "room_enc", "device_enc",
        "avg_temperature", "avg_humidity", "usage_rate",
    ]
    target_col = "total_kwh"

    X = df[feature_cols].copy()
    y = df[target_col].copy()

    print(f"  Features: {feature_cols}")
    print(f"  Target: {target_col}")
    print(f"  X shape: {X.shape}, y shape: {y.shape}")

    return X, y, feature_cols, le_room, le_device


def train_models(X_train, X_test, y_train, y_test, feature_cols):
    """Train and evaluate multiple models."""
    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        ),
    }

    results = {}

    for name, model in models.items():
        print(f"\nTraining {name}...")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))

        print(f"  R² Score:  {r2:.4f}")
        print(f"  MAE:       {mae:.4f}")
        print(f"  RMSE:      {rmse:.4f}")

        # Feature importances (for tree-based models)
        importances = {}
        if hasattr(model, "feature_importances_"):
            for feat, imp in zip(feature_cols, model.feature_importances_):
                importances[feat] = round(float(imp), 4)
        elif hasattr(model, "coef_"):
            for feat, coef in zip(feature_cols, model.coef_):
                importances[feat] = round(float(abs(coef)), 4)

        results[name] = {
            "model": model,
            "r2": round(r2, 4),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "predictions": y_pred,
            "feature_importances": importances,
        }

    return results


def save_outputs(results: dict, y_test, X_test, best_name: str,
                 le_room, le_device, output_dir: str):
    """Save the best model, metrics, and training results."""
    os.makedirs(output_dir, exist_ok=True)

    best = results[best_name]

    # Save model
    model_path = os.path.join(output_dir, "model.pkl")
    joblib.dump(best["model"], model_path)
    print(f"\nSaved best model ({best_name}) to {model_path}")

    # Save encoders
    encoders_path = os.path.join(output_dir, "encoders.pkl")
    joblib.dump({"room": le_room, "device": le_device}, encoders_path)
    print(f"Saved encoders to {encoders_path}")

    # Save metrics
    metrics = {}
    for name, res in results.items():
        metrics[name] = {
            "r2": res["r2"],
            "mae": res["mae"],
            "rmse": res["rmse"],
            "feature_importances": res["feature_importances"],
        }
    metrics["best_model"] = best_name

    metrics_path = os.path.join(output_dir, "model_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics to {metrics_path}")

    # Save training results (actual vs predicted)
    results_df = pd.DataFrame({
        "actual": y_test.values,
        "predicted": best["predictions"],
    })
    # Sample 2000 points for visualization
    if len(results_df) > 2000:
        results_df = results_df.sample(2000, random_state=42)
    results_path = os.path.join(output_dir, "training_results.csv")
    results_df.to_csv(results_path, index=False)
    print(f"Saved training results to {results_path}")


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "daily_aggregates.csv")

    if not os.path.exists(data_path):
        print(f"Error: Daily aggregate data not found at {data_path}")
        print("Run data_processor.py first.")
        sys.exit(1)

    df = load_data(data_path)
    X, y, feature_cols, le_room, le_device = prepare_features(df)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"\nTrain: {X_train.shape[0]} samples | Test: {X_test.shape[0]} samples")

    # Train models
    results = train_models(X_train, X_test, y_train, y_test, feature_cols)

    # Pick best model by R²
    best_name = max(results, key=lambda k: results[k]["r2"])
    print(f"\n{'=' * 50}")
    print(f"BEST MODEL: {best_name} (R² = {results[best_name]['r2']:.4f})")
    print(f"{'=' * 50}")

    # Save outputs
    ml_dir = os.path.dirname(os.path.abspath(__file__))
    save_outputs(results, y_test, X_test, best_name, le_room, le_device, ml_dir)

    print("\nTraining complete!")


if __name__ == "__main__":
    main()
