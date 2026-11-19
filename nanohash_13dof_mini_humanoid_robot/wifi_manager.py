# wifi_manager.py
# Connects to the home Wi-Fi and returns the IP address (or None on failure).

import time
import network

import config
from logger import log, error


def connect(on_wait=None):
    """Connect in station mode.
    on_wait: optional function called while waiting (used to animate the face).
    """
    try:
        iface = network.WLAN.IF_STA
    except AttributeError:
        iface = network.STA_IF

    wifi = network.WLAN(iface)
    wifi.active(True)
    try:
        wifi.config(txpower=config.WIFI_TX_POWER)
    except Exception as e:
        error("Cannot set tx power: " + str(e))

    if not wifi.isconnected():
        log("Connecting to Wi-Fi: " + config.WIFI_SSID)
        wifi.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

        deadline = time.ticks_add(time.ticks_ms(), config.WIFI_TIMEOUT_S * 1000)
        while not wifi.isconnected() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if on_wait:
                on_wait()
            time.sleep_ms(50)

    if not wifi.isconnected():
        error("Wi-Fi connection failed - check SSID and password")
        return None

    ip, subnet, gateway, _ = wifi.ifconfig()
    log("==============================")
    log("Wi-Fi connected")
    log("IP address: " + ip)
    log("Subnet: " + subnet + "  Gateway: " + gateway)
    log("==============================")
    return ip
