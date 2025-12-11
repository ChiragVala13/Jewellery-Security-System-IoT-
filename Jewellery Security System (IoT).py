# JEWELRY SECURITY SYSTEM (Raspberry Pi + ADS1115 + ThingSpeak)
# ==============================================================

import RPi.GPIO as GPIO
import time
import datetime
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import requests

# --- ThingSpeak Configuration ---
THINGSPEAK_API_KEY = "D5K4YI8IGHUBK2OA"   # Replace with your ThingSpeak WRITE API Key
THINGSPEAK_URL = "https://api.thingspeak.com/update"
THINGSPEAK_INTERVAL = 30   # seconds

# --- ADS1115 / Sensor Setup ---
FSR_THRESHOLD = 500         # Adjust threshold based on FSR calibration
ADC_READ_INTERVAL = 0.5     # seconds
DEVICE_ID = "JEWELRY_COUNTER_001"

# --- GPIO Pin Configuration (BCM) ---
LED_PIN = 26                # Red LED output
RELAY_PIN = 17              # Relay or Buzzer output
RELAY_ACTIVE = GPIO.HIGH

# --- Security Time Window (24-Hour Format) ---
SECURITY_START_HOUR = 22    # 10 PM
SECURITY_END_HOUR = 6       # 6 AM

# --- Global State Variables ---
armed = False
alarm_active = False
last_update = 0

# --- GPIO Setup ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.output(RELAY_PIN, not RELAY_ACTIVE)
GPIO.output(LED_PIN, GPIO.LOW)

# --- I2C Setup for ADS1115 ---
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)
    ads.gain = 2/3
    chan = AnalogIn(ads, 0)  # Use channel A0
    print("✅ ADS1115 connected successfully.")
except Exception as e:
    print(f"❌ ADS1115 setup failed: {e}")
    GPIO.cleanup()
    exit()

# --- ThingSpeak Update Function ---
def update_thingspeak(fsr_value, status_code):
    """
    Field 1: FSR value
    Field 2: Status (0=Disarmed, 1=Armed, 2=Alarm Triggered)
    """
    try:
        payload = {"api_key": THINGSPEAK_API_KEY,
                   "field1": fsr_value,
                   "field2": status_code}
        r = requests.post(THINGSPEAK_URL, data=payload, timeout=5)
        if r.status_code == 200:
            print(f"📡 Uploaded to ThingSpeak: FSR={fsr_value} | Status={status_code}")
        else:
            print(f"⚠️ ThingSpeak HTTP {r.status_code}")
    except Exception as e:
        print(f"⚠️ ThingSpeak update error: {e}")

# --- Helper Functions ---
def read_fsr():
    """Read analog FSR value from ADS1115."""
    return chan.value

def is_security_time():
    """Check if current time is within the defined security window."""
    hour = datetime.datetime.now().hour
    if SECURITY_START_HOUR <= SECURITY_END_HOUR:
        return SECURITY_START_HOUR <= hour < SECURITY_END_HOUR
    else:
        return (hour >= SECURITY_START_HOUR) or (hour < SECURITY_END_HOUR)

def activate_alarm(fsr_val):
    """Trigger alarm (relay + LED + ThingSpeak alert)."""
    global alarm_active
    if not alarm_active:
        alarm_active = True
        GPIO.output(RELAY_PIN, RELAY_ACTIVE)
        print(f"🚨 ALERT: Ornament Removed! FSR={fsr_val}")
        update_thingspeak(fsr_val, 2)

def deactivate_alarm(reason="Condition Normal"):
    """Turn off alarm and reset status."""
    global alarm_active
    GPIO.output(RELAY_PIN, not RELAY_ACTIVE)
    if alarm_active:
        alarm_active = False
        print(f"✅ Alarm cleared: {reason}")
    status = 1 if armed else 0
    update_thingspeak(read_fsr(), status)

def update_led():
    """Flash LED when alarm active, ON when armed, OFF when disarmed."""
    if alarm_active:
        flash = (time.time() * 10) % 2 < 1
        GPIO.output(LED_PIN, GPIO.HIGH if flash else GPIO.LOW)
    elif armed:
        GPIO.output(LED_PIN, GPIO.HIGH)
    else:
        GPIO.output(LED_PIN, GPIO.LOW)

# --- Main Loop ---
print("\n--- JEWELRY SECURITY SYSTEM ACTIVE ---")
print(f"Device: {DEVICE_ID}")
print(f"Monitoring Window: {SECURITY_START_HOUR}:00 → {SECURITY_END_HOUR}:00\n")

try:
    while True:
        fsr_val = read_fsr()
        update_led()

        # Arm system automatically during security hours
        armed = is_security_time()

        if armed:
            if fsr_val < FSR_THRESHOLD and not alarm_active:
                activate_alarm(fsr_val)
            elif alarm_active and fsr_val >= FSR_THRESHOLD:
                deactivate_alarm("Jewelry replaced")
        else:
            if alarm_active:
                deactivate_alarm("Outside security hours")

        # Periodic ThingSpeak update
        if time.time() - last_update >= THINGSPEAK_INTERVAL:
            status = 2 if alarm_active else (1 if armed else 0)
            update_thingspeak(fsr_val, status)
            last_update = time.time()

        time.sleep(ADC_READ_INTERVAL)

except KeyboardInterrupt:
    print("\n🛑 System stopped manually.")
finally:
    deactivate_alarm("System Shutdown")
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("🧹 GPIO cleanup complete. System off.")