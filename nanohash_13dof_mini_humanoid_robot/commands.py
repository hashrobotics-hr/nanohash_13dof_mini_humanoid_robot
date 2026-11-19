# commands.py
# Handles every JSON command coming from the web UI.
#
#   {"cmd":"servo","channel":0,"angle":90,"time":0}
#   {"cmd":"step","angles":[... 16 values ...],"time":1000}
#   {"cmd":"move","movement":"say_hi","time":1000,"count":1}
#   {"cmd":"movements"}
#   {"cmd":"face","expression":"happy"}
#   {"cmd":"expressions"}
#   {"cmd":"touch"}                      -> read touch-interaction state
#   {"cmd":"touch","enabled":true}       -> turn touch-interaction on/off

import time

import config
from logger import log, error


class CommandHandler:

    def __init__(self, robot, touch_mode):
        self.robot = robot
        self.touch_mode = touch_mode
        self._routes = {
            "servo": self.handle_servo,
            "step": self.handle_step,
            "move": self.handle_move,
            "movements": self.handle_movements,
            "face": self.handle_face,
            "expressions": self.handle_expressions,
            "touch": self.handle_touch,
        }

    # ------------------------------------------------------------------
    def process(self, command):
        cmd = command.get("cmd")
        log("CMD = " + str(cmd))

        handler = self._routes.get(cmd)
        if handler is None:
            return self._fail("Unknown command")
        try:
            return handler(command)
        except OSError as e:
            self.robot.mark_i2c_fault(e)
            return self._fail("I2C device not responding (check servo power / wiring)")
        except Exception as e:
            return self._fail("Command failed: " + str(e))

    @staticmethod
    def _fail(message):
        error(message)
        return {"status": "error", "message": message}

    # ------------------------------------------------------------------
    # servos
    # ------------------------------------------------------------------
    def handle_servo(self, c):
        try:
            channel = int(c["channel"])
            angle = int(c["angle"])
            time_ms = int(c.get("time", 0))
        except Exception:
            return self._fail("Invalid servo command")

        if channel < 0 or channel >= config.SERVO_COUNT:
            return self._fail("Channel must be 0-15")
        if angle < 0 or angle > 180:
            return self._fail("Angle must be 0-180")
        time_ms = max(0, time_ms)

        log("SERVO CH%d -> %d (%dms)" % (channel, angle, time_ms))
        self.robot.servo.move_servo(channel, angle, time_ms)

        return {"status": "ok", "cmd": "servo",
                "channel": channel, "angle": angle, "time": time_ms}

    def handle_step(self, c):
        try:
            angles = [int(a) for a in c["angles"]]
            time_ms = int(c.get("time", 1000))
        except Exception:
            return self._fail("Invalid step command")

        if len(angles) != config.SERVO_COUNT:
            return self._fail("Exactly 16 angles required")
        for a in angles:
            if a < 0 or a > 180:
                return self._fail("Angles must be 0-180")
        time_ms = max(0, time_ms)

        log("STEP " + str(angles) + " in %dms" % time_ms)
        start = time.ticks_ms()
        self.robot.servo.move_all(angles, time_ms)
        log("STEP complete in %dms" % time.ticks_diff(time.ticks_ms(), start))

        return {"status": "ok", "cmd": "step", "angles": angles, "time": time_ms}

    # ------------------------------------------------------------------
    # predefined movements
    # ------------------------------------------------------------------
    def handle_movements(self, c):
        return {"status": "ok", "cmd": "movements",
                "movements": self.robot.movement_names()}

    def handle_move(self, c):
        name = c.get("movement")
        if not name or name not in self.robot.movement_names():
            return self._fail("Unknown movement: " + str(name))

        try:
            time_ms = max(0, int(c.get("time", 1000)))
            count = max(1, int(c.get("count", 1)))
        except Exception:
            return self._fail("time and count must be numbers")

        log("MOVE %s time=%dms count=%d" % (name, time_ms, count))
        self.robot.run_movement(name, time_ms, count)
        log("MOVE " + name + " complete")

        return {"status": "ok", "cmd": "move", "movement": name,
                "time": time_ms, "count": count,
                "angles": self.robot.servo_angles()}

    # ------------------------------------------------------------------
    # facial expressions
    # ------------------------------------------------------------------
    def handle_face(self, c):
        if not self.robot.has_face:
            return self._fail("OLED display not available")

        name = c.get("expression")
        if not name:
            return self._fail("expression is required")

        proper = self.robot.set_expression(name)
        if proper is None:
            return self._fail("Unknown expression: " + str(name))

        log("FACE " + proper)
        return {"status": "ok", "cmd": "face", "expression": proper}

    def handle_expressions(self, c):
        return {"status": "ok", "cmd": "expressions",
                "expressions": self.robot.expression_names(),
                "current": self.robot.expression,
                "touch": self.touch_mode.enabled}

    # ------------------------------------------------------------------
    # touch interaction on/off
    # ------------------------------------------------------------------
    def handle_touch(self, c):
        if "enabled" in c:
            self.touch_mode.set_enabled(bool(c["enabled"]))
        return {"status": "ok", "cmd": "touch", "enabled": self.touch_mode.enabled}
