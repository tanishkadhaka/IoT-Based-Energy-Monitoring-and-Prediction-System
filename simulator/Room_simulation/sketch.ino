#include <DHT.h>

#define DHTPIN 14
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);

// Pins
int lightPin = 5;
int acRelay = 2;
int heaterRelay = 18;

// We will simulate these instead of reading physical pins to get perfect curves, 
// but we keep the pin definitions for the circuitry to stay valid.
int ldrPin = 34;
int pirPin = 13;

// Servo (PWM using LEDC)
int servoPin = 4;
int pwmChannel = 0;
int pwmFreq = 50;
int pwmResolution = 16;

// States
bool lightOn = false;
bool fanOn = false;
bool acOn = false;
bool heaterOn = false;

// ── Simulation State Machine Variables ──
int simHour = 6;     // Start at 6 AM
int simMinute = 0;
float currentTemp = 24.0;
float currentHum = 60.0;
float currentLdr = 200.0;
int currentMotion = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);  // Give serial monitor time to attach

  // Initialize output pins
  pinMode(lightPin, OUTPUT);
  pinMode(acRelay, OUTPUT);
  pinMode(heaterRelay, OUTPUT);

  // Setup PWM for servo
  ledcSetup(pwmChannel, pwmFreq, pwmResolution);
  ledcAttachPin(servoPin, pwmChannel);

  dht.begin();

  // Print header on boot so the Python reader knows we're alive
  Serial.println("=== ESP32 Room Simulation Started ===");
  Serial.println("DATA_START");
}

void loop() {
  // ── 1. Update Simulated Clock ──
  // Advance time by 15 simulation minutes every loop iteration
  simMinute += 15;
  if (simMinute >= 60) {
    simHour = (simHour + 1) % 24;
    simMinute = 0;
  }

  // ── 2. Calculate Targets Based on Time ──
  float targetTemp = 25.0;
  float targetHum = 60.0;
  float targetLdr = 100.0;
  int motionProb = 10;

  // Time-based curve logic
  if (simHour >= 0 && simHour < 6) {
    targetTemp = 23.0;
    targetHum = 65.0;
    targetLdr = 50.0;
    motionProb = 2; // Sleeping
  } else if (simHour >= 6 && simHour < 9) {
    targetTemp = 26.0;
    targetHum = 55.0;
    targetLdr = 1500.0;
    motionProb = 80; // Morning rush
  } else if (simHour >= 9 && simHour < 12) {
    targetTemp = 29.0;
    targetHum = 50.0;
    targetLdr = 3000.0;
    motionProb = 30; // Day time
  } else if (simHour >= 12 && simHour < 16) {
    targetTemp = 32.5; // Peak heat
    targetHum = 40.0;
    targetLdr = 3500.0;
    motionProb = 20; // Afternoon lull
  } else if (simHour >= 16 && simHour < 19) {
    targetTemp = 29.0;
    targetHum = 50.0;
    targetLdr = 1200.0;
    motionProb = 70; // Evening return
  } else {
    targetTemp = 25.0;
    targetHum = 60.0;
    targetLdr = 200.0;
    motionProb = 40; // Night
  }

  // ── 3. Apply Smooth Trends (No Jumps!) ──
  // Slowly move current values towards targets
  
  // Temperature trends slowly (~0.2 degrees per step)
  if (currentTemp < targetTemp) currentTemp += 0.25;
  else if (currentTemp > targetTemp) currentTemp -= 0.25;
  currentTemp += (random(-5, 6) / 100.0); // Add tiny stochastic noise +/- 0.05

  // Humidity trends slowly
  if (currentHum < targetHum) currentHum += 0.5;
  else if (currentHum > targetHum) currentHum -= 0.5;
  currentHum += (random(-10, 11) / 10.0); // Noise +/- 1.0

  // Light transitions faster
  if (currentLdr < targetLdr) currentLdr += 150.0;
  else if (currentLdr > targetLdr) currentLdr -= 150.0;
  currentLdr += random(-20, 20); // Noise
  if (currentLdr < 0) currentLdr = 0;

  // ── 4. Apply Stochastic Probability for Motion ──
  currentMotion = (random(0, 100) < motionProb) ? 1 : 0;

  // ── 5. Control Logic ──
  acOn = (currentTemp > 30.0);
  heaterOn = (currentTemp < 22.0);
  lightOn = (currentLdr < 500);
  fanOn = (currentMotion == 1);

  // ── 6. Actuator Outputs ──
  digitalWrite(acRelay, acOn ? HIGH : LOW);
  digitalWrite(heaterRelay, heaterOn ? HIGH : LOW);
  digitalWrite(lightPin, lightOn ? HIGH : LOW);

  // Servo control (fan)
  if (fanOn) {
    ledcWrite(pwmChannel, 4915);  // ~2ms pulse → rotate
  } else {
    ledcWrite(pwmChannel, 1638);  // ~1ms pulse → stop
  }

  // ── 7. Power Calculation ──
  float totalPower = 0;
  if (acOn) totalPower += 1500;
  if (heaterOn) totalPower += 2000;
  if (fanOn) totalPower += 75;
  if (lightOn) totalPower += 60;

  float voltage = 230.0;
  float current = totalPower / voltage;

  // ── 8. JSON Serial Output ──
  // One JSON object per line — parsed by serial_reader.py
  Serial.print("{");
  Serial.print("\"time\":\""); 
  if (simHour < 10) Serial.print("0");
  Serial.print(simHour); Serial.print(":"); 
  if (simMinute < 10) Serial.print("0");
  Serial.print(simMinute); Serial.print("\"");
  
  Serial.print(",\"temp\":"); Serial.print(currentTemp, 2);
  Serial.print(",\"humidity\":"); Serial.print(currentHum, 1);
  Serial.print(",\"ldr\":"); Serial.print(int(currentLdr));
  Serial.print(",\"motion\":"); Serial.print(currentMotion);
  Serial.print(",\"ac\":"); Serial.print(acOn ? 1 : 0);
  Serial.print(",\"heater\":"); Serial.print(heaterOn ? 1 : 0);
  Serial.print(",\"fan\":"); Serial.print(fanOn ? 1 : 0);
  Serial.print(",\"light\":"); Serial.print(lightOn ? 1 : 0);
  Serial.print(",\"power\":"); Serial.print(totalPower, 1);
  Serial.print(",\"current\":"); Serial.print(current, 2);
  Serial.print(",\"voltage\":"); Serial.print(voltage, 1);
  Serial.println("}");

  // Wait 2 seconds before next tick
  delay(2000);
}