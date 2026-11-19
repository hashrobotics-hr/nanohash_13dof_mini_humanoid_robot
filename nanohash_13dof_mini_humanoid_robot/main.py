# main.py - NanoHash entry point.
#
# Files:
#   config.py       settings (Wi-Fi, pins, timings)
#   robot.py        hardware: servos, movements, OLED face, touch sensor
#   commands.py     web commands (servo, step, move, face, touch ...)
#   interaction.py  random cute reactions when the touch sensor is pressed
#   web_server.py   HTTP plumbing
#   wifi_manager.py Wi-Fi connection
#
# Main loop = animate face + check touch + serve web requests.

import time

import config
import wifi_manager
from logger import log, error
from robot import Robot
from interaction import TouchInteraction
from commands import CommandHandler
from web_server import WebServer


# ---------------- build everything ----------------
robot = Robot()
touch_mode = TouchInteraction(robot)
commands = CommandHandler(robot, touch_mode)

# ---------------- network ----------------
robot.set_expression("Thinking")
ip = wifi_manager.connect(on_wait=robot.update_face)

server = None
if ip:
    server = WebServer(commands)
    server.start(ip)
    robot.set_expression("Normal")
    # Show the address so you can open the web UI without a laptop.
    robot.show_message(["NanoHash IP", ip], config.IP_DISPLAY_MS)
else:
    # Still useful: the touch sensor works without Wi-Fi.
    robot.set_expression("Sad")
    robot.show_message(["No Wi-Fi", "Touch mode"], config.IP_DISPLAY_MS)
    error("Running without web control (touch only)")

log("Ready")

# ---------------- main loop ----------------
while True:
    try:
        robot.update_face()      # keep the face animating
        touch_mode.update()      # self-action from the touch sensor
        if server:
            server.poll()        # web UI commands
    except Exception as e:
        error("Main loop: " + str(e))
    time.sleep_ms(5)
