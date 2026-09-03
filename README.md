⚡ IoT-Based Energy Monitoring and Prediction System
A Comprehensive IoT + Machine Learning Approach to Residential Energy Analytics

An end-to-end IoT-enabled energy monitoring and prediction system built around an ESP32 microcontroller (simulated via Wokwi), a suite of environmental sensors, a Random Forest prediction pipeline, and a real-time Flask + Chart.js web dashboard — complete with Indian slab-tariff cost estimation and autonomous anomaly alerts.

📌 Overview

Residential electricity consumption accounts for roughly 24% of India's total electricity demand, and the country's progressive slab-based tariff system means costs rise sharply with higher usage. This project builds a low-cost, IoT-driven alternative to expensive smart-metering systems — using sensor data, machine learning, and financial modeling to help users understand and predict their energy usage and costs.

The system captures environmental and occupancy data across five room profiles (Living Room, Bedroom, Kitchen, Office, Bathroom), expands it into a realistic twelve-month dataset, trains a Random Forest Regressor on it, and serves predictions and cost estimates through an interactive web dashboard.

✨ Features
🌡️ Multi-sensor data acquisition — temperature, humidity, motion, and ambient light via ESP32 + DHT22, PIR, and LDR sensors
🔁 Temporal scaling pipeline — expands ~500 simulated readings into a 2,500-record, twelve-month dataset across 5 rooms
🌲 Random Forest Regressor — predicts daily/monthly energy consumption (R² ≈ 0.921, MAE = 0.21 kWh/day)
💰 Indian slab-tariff cost engine — computes monthly electricity costs using a progressive tariff model
📊 Real-time Flask dashboard — live trend graphs, monthly aggregates, and feature-importance charts via Chart.js
🚨 Autonomous anomaly detection — flags abnormal power usage (e.g., appliances left on) with actionable alerts
🔌 Relay control integration — supports automated load-shifting recommendations
🖥️ Tech Stack
Category	Tools & Technologies
Microcontroller	ESP32 (simulated via Wokwi)
Sensors	DHT22 (temp/humidity), PIR HC-SR501 (motion), LDR (light)
Backend / ML	Python, Flask, scikit-learn (Random Forest)
Data Pipeline	pandas, NumPy
Frontend / Visualization	Chart.js, HTML, CSS, JavaScript
Communication	RFC2217 serial protocol
🏗️ System Architecture

The system is organized into four functional layers:

Edge Hardware Layer → Data Ingestion & Scaling Layer → ML Layer → Frontend/API Layer
Wokwi ESP32 simulator streams JSON sensor packets every 2 seconds via RFC2217 (port 4000/4001) to serial_reader.py
building_scaler.py expands captured readings across twelve calendar months using five distinct room profiles
data_processor.py performs feature engineering on the expanded dataset
The trained model (model.pkl) is loaded into the Flask backend (app.py), which serves predictions to the dashboard
🔧 Hardware Components
Component	Connection	Function
DHT22	GPIO 14 (10kΩ pull-up)	Temperature (±0.1°C) & humidity (±0.1% RH) sensing
PIR Motion Sensor (HC-SR501)	GPIO 13	Occupancy detection (7m range, 5s hold time)
LDR	GPIO 34 (ADC, 10kΩ voltage divider)	Ambient light sensing (0–100 lux, 12-bit resolution)
📂 Dataset
Generation: 500 simulated Wokwi readings (~16 minutes) expanded to 12 months via temporal scaling
Size: 2,500 records across 5 rooms
File: raw_sensor_data.csv
Feature	Type	Description
Temperature	°C (float)	Ambient temperature from DHT22
Humidity	% RH (float)	Relative humidity from DHT22
Motion	Binary	Occupancy status from PIR
Light	Lux (int)	Ambient illumination from LDR
relay_state	Binary	Appliance load status
Room	Categorical	Living Room, Bedroom, Kitchen, Office, Bathroom
device_type	Categorical	AC, Fan, Heater, Light, TV
energy_kwh	kWh (float)	Computed energy for the interval
Timestamp	Datetime	ISO 8601 reading timestamp
🤖 Machine Learning Model

Algorithm: Random Forest Regressor (scikit-learn v1.3) Parameters: n_estimators=200, max_depth=None, min_samples_split=2 Split: 80% training / 20% testing

Metric	Value
MAE	0.21 kWh/day
RMSE	0.31 kWh/day
R² Score	0.921

Prediction Algorithm:

Inputs: Room, Device Type, Month, Temperature, Humidity
1. Encode categorical inputs numerically
2. Build feature vector X = [Room_num, Device_num, Month_num, Temp, Humidity]
3. Load pre-trained model (model.pkl)
4. Predict daily energy: E_daily = RF.predict(X)
5. Compute monthly energy: E_monthly = E_daily × 30
6. Apply Indian slab tariff:
   - ≤200 kWh: Cost = E_monthly × ₹4.0
   - ≤400 kWh: Cost = 200×₹4.0 + (E_monthly−200)×₹6.0
   - >400 kWh: Cost = 200×₹4.0 + 200×₹6.0 + (E_monthly−400)×₹8.0
Output: E_pred (kWh/day), Cost (INR/month)
📊 Results
Sensor acquisition: Zero packet loss across 500 samples; temperature range 22.1°C–38.7°C, humidity 38–89% RH
Dashboard: 5.3K kWh total consumption tracked, ₹41.6K total cost, 2.0 kW peak power, across 5 rooms
Best/worst room accuracy: Bedroom (MAE = 0.018 kWh) vs. Kitchen (MAE = 0.029 kWh, due to meal-time spikes)
Anomaly detection: 4 critical anomalies correctly flagged in testing with zero false positives over a 30-minute run
Benchmark comparison: Outperforms 5 reference works on combined dataset size, multi-room coverage, tariff realism, and dashboard functionality
🚀 Getting Started
Prerequisites
bash
Python 3.8+
pip
Wokwi (VS Code extension) — for hardware simulation
Installation
bash
# Clone the repository
git clone https://github.com/<your-username>/iot-energy-monitoring.git
cd iot-energy-monitoring

# Install dependencies
pip install -r requirements.txt
Run the Pipeline
bash
# Start the serial reader (with Wokwi simulation running)
python serial_reader.py

# Generate/scale the twelve-month dataset
python building_scaler.py

# Process features
python data_processor.py

# Launch the dashboard
python app.py
📁 Project Structure
iot-energy-monitoring/
├── app.py                  # Flask backend & dashboard server
├── serial_reader.py         # Reads JSON sensor data via RFC2217
├── building_scaler.py       # Temporal scaling across 12 months
├── data_processor.py        # Feature engineering
├── model.pkl                 # Trained Random Forest model
├── raw_sensor_data.csv       # Generated dataset (2,500 records)
├── wokwi/                     # Wokwi simulation files (diagram.json, sketch.ino)
├── static/ & templates/       # Dashboard frontend (Chart.js, HTML, CSS)
├── requirements.txt
└── README.md
🔮 Future Scope
🔌 Deployment on real physical ESP32 hardware with MQTT-based cloud connectivity (AWS IoT Core / ThingSpeak)
📱 Android app for remote relay control and push notifications
⏱️ Hourly forecasting using LSTM models
💳 Integration with live Indian power company APIs for real-time tariff updates


📄 License

This project was developed as part of an academic course project. Feel free to fork and build upon it for educational purposes.

⭐ If you found this project useful, consider giving it a star!
