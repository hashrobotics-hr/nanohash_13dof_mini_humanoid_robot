# robot.py
# Owns all the hardware: I2C bus, servos, movements, OLED face, touch sensor.
# Everything else (web commands, touch reactions) talks to the robot through
# this one class, so the hardware setup exists in exactly one place.

import time

from machine import I2C, Pin

import config
from logger import log, error
from servo import Servos
from hashmoves import HashMoves
from ttp223touch import TouchSensor


class Robot:

    def __init__(self):
        self.face = None
        self.expression = None
        self._expr_lookup = {}
        self._oled = None
        self._overlay = None       # list of text lines while a message is shown
        self._overlay_until = 0
        self._overlay_drawn = False
        self._fault_at = None      # ticks_ms of the last I2C error, None = bus OK

        self.i2c = I2C(
            config.I2C_ID,
            sda=Pin(config.I2C_SDA),
            scl=Pin(config.I2C_SCL),
            freq=config.I2C_FREQ,
        )
        log("I2C devices: " + str([hex(a) for a in self.i2c.scan()]))

        # Face first, so the robot already looks alive while the servos move
        # to their start pose.
        self._init_face()

        self.servo = Servos(self.i2c)
        if config.FACE_ANIMATE_DURING_MOVES:
            self.servo.on_wait = self.update_face

        log("Moving to initial position...")
        self.moves = HashMoves()
        self.moves.initialize(self.i2c, self.servo)
        log("Initial position complete")

        self.touch = TouchSensor(config.TOUCH_PIN)

    # ------------------------------------------------------------------
    # face
    # ------------------------------------------------------------------
    def _init_face(self):
        try:
            from sh1106 import SH1106_I2C
            from nanoface import NanoFace

            oled = SH1106_I2C(
                config.OLED_WIDTH, config.OLED_HEIGHT,
                self.i2c, addr=config.OLED_ADDR,
            )
            self._oled = oled
            self.face = NanoFace(oled)
            self._expr_lookup = {n.lower(): n for n in NanoFace.EXPRESSIONS}
            self.expression = self.face.expression
            log("OLED face ready")
        except Exception as e:
            self.face = None
            error("OLED not available, continuing without face: " + str(e))

    @property
    def has_face(self):
        return self.face is not None

    def expression_names(self):
        if not self.face:
            return []
        return list(self.face.EXPRESSIONS)

    def set_expression(self, name):
        """Show an expression (case-insensitive). Returns its proper name,
        or None if the name is unknown / there is no display."""
        if not self.face:
            return None
        proper = self._expr_lookup.get(str(name).strip().lower())
        if proper is None:
            return None
        try:
            self.face.set_expression(proper)   # clears the screen ...
        except OSError as e:
            self.mark_i2c_fault(e)
        self._overlay_drawn = False            # ... so redraw any message on top
        self.expression = proper
        return proper

    def update_face(self):
        """Advance the face animation. Call this often."""
        if self._fault_at is not None:
            # Bus had an error: only retry every I2C_RETRY_MS, never spam.
            if time.ticks_diff(time.ticks_ms(), self._fault_at) < config.I2C_RETRY_MS:
                return
            if not self.recover():
                return
        if not self.face:
            return
        try:
            if self._overlay is not None:
                self._update_overlay()
                return
            self.face.update()
        except OSError as e:
            self.mark_i2c_fault(e)

    # ------------------------------------------------------------------
    # timed text message on the OLED (e.g. the IP address at start-up)
    # Non-blocking: the face is replaced by the text for duration_ms, then
    # the face comes back. Web UI and touch keep working meanwhile.
    # ------------------------------------------------------------------
    def show_message(self, lines, duration_ms):
        """lines: list of short strings (max 16 chars each, 8 px font)."""
        if not self._oled or duration_ms <= 0:
            return
        self._overlay = list(lines)
        self._overlay_until = time.ticks_add(time.ticks_ms(), duration_ms)
        self._overlay_drawn = False

    def _update_overlay(self):
        oled = self._oled
        if time.ticks_diff(time.ticks_ms(), self._overlay_until) >= 0:
            self._overlay = None
            oled.fill(0)
            oled.show()
            return
        if self._overlay_drawn:
            return                      # static text, draw once
        oled.fill(0)
        n = len(self._overlay)
        top = (config.OLED_HEIGHT - n * 16 + 8) // 2
        for i, text in enumerate(self._overlay):
            x = max(0, (config.OLED_WIDTH - len(text) * 8) // 2)
            oled.text(text, x, top + i * 16, 1)
        oled.show()
        self._overlay_drawn = True

    # ------------------------------------------------------------------
    # I2C fault handling (a device stops answering -> ENODEV)
    # ------------------------------------------------------------------
    def mark_i2c_fault(self, exc):
        """Remember that the bus failed so the face pauses until recovery."""
        if self._fault_at is None:
            error("I2C error: " + str(exc))
            self.recover(report_only=True)
        self._fault_at = time.ticks_ms()

    def recover(self, report_only=False):
        """Scan the bus, report which device is missing and, if both are back,
        re-initialise them. Returns True when everything is working again."""
        try:
            found = self.i2c.scan()
        except OSError as e:
            error("I2C scan failed: " + str(e))
            self._fault_at = time.ticks_ms()
            return False

        wanted = (("OLED", config.OLED_ADDR), ("PCA9685", config.PCA_ADDR))
        missing = [n + " " + hex(a) for n, a in wanted
                   if a not in found and (n != "OLED" or self.face)]
        log("I2C devices now: " + str([hex(a) for a in found]))
        if missing:
            error("Missing on I2C bus: " + ", ".join(missing)
                  + "  (check power / wiring)")
            self._fault_at = time.ticks_ms()
            return False
        if report_only:
            return False

        try:
            self.servo.reinit()
            if self._oled:
                self._oled.init_display()
        except OSError as e:
            error("I2C re-init failed: " + str(e))
            self._fault_at = time.ticks_ms()
            return False

        self._fault_at = None
        self._overlay_drawn = False
        log("I2C recovered")
        return True

    # ------------------------------------------------------------------
    # movements
    # ------------------------------------------------------------------
    def movement_names(self):
        names = []
        for name in dir(self.moves):
            if name.startswith("_") or name == "initialize" or name.isupper():
                continue
            try:
                if callable(getattr(self.moves, name)):
                    names.append(name)
            except Exception:
                pass
        return names

    def run_movement(self, name, time_ms, count):
        try:
            getattr(self.moves, name)(time_ms, count)
        except OSError as e:
            self.mark_i2c_fault(e)
            raise

    def servo_angles(self):
        return [int(a) for a in self.servo._servopos]
