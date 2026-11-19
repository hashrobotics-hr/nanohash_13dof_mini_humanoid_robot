# config.py
# All user-tunable settings for NanoHash live here.

# ---------------- Wi-Fi ----------------
WIFI_SSID = "Your Wifi SSID Name"
WIFI_PASSWORD = "Your Wifi Password"
WIFI_TX_POWER = 8.5       # dBm, lowered for ESP32-C3 SuperMini stability
WIFI_TIMEOUT_S = 20

# ---------------- Web server ----------------
HTTP_PORT = 80
HTML_FILE = "index.html"

# ---------------- I2C bus (PCA9685 + OLED share it) ----------------
I2C_ID = 0
I2C_SDA = 8
I2C_SCL = 9
I2C_FREQ = 400000
I2C_RETRY_MS = 2000           # after an I2C error, wait this long between recovery attempts

# ---------------- Devices ----------------
SERVO_COUNT = 16
PCA_ADDR = 0x40
OLED_ADDR = 0x3C
OLED_WIDTH = 128
OLED_HEIGHT = 64
TOUCH_PIN = 10

# Keep the face animating while a movement is running.
# If movements look jerky, set this to False.
FACE_ANIMATE_DURING_MOVES = True

# Show the IP address on the OLED after start-up (0 = don't show).
IP_DISPLAY_MS = 10000

# ---------------- Touch interaction ----------------
TOUCH_ENABLED_AT_BOOT = True
TOUCH_COOLDOWN_MS = 1500      # minimum pause between two reactions
TOUCH_FACE_HOLD_MS = 4000     # how long a reaction face stays before going back to Normal
