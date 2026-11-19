# interaction.py
# Touch-sensor behaviour: when the robot is touched it picks a random cute
# reaction (a facial expression, usually together with a body movement).
# The web UI keeps working at the same time; it can also switch this on/off.

import random
import time

import config
from logger import log, error

# (expression, movement, move_time_ms, repeat_count)
# movement None = just make a cute face.
# Movements here all finish back in the rest pose.
REACTIONS = (
    ("Happy",       "say_hi",              450, 1),
    ("Excited",     "cheer",               350, 2),
    ("Laughing",    "side_shake",          450, 2),
    ("Love",        "wave_both",           450, 1),
    ("Wink",        "wave_left",           450, 1),
    ("Surprised",   "head_shake",          350, 2),
    ("Curious",     "scan",                450, 1),
    ("Proud",       "flying_move",         400, 2),
    ("Happy",       "twist",               400, 2),
    ("Embarrassed", "head_shake",          400, 2),
    ("Love",        "right_slide_wave",    450, 2),
    ("Excited",     "arms_flap",           350, 3),
    ("Confident",   "hand_straight_shake", 400, 2),
    ("Love",        None,                  0,   0),
    ("Wink",        None,                  0,   0),
    ("Happy",       None,                  0,   0),
    ("Embarrassed", None,                  0,   0),
)

IDLE_EXPRESSION = "Normal"


class TouchInteraction:

    def __init__(self, robot):
        self.robot = robot
        self.enabled = config.TOUCH_ENABLED_AT_BOOT
        self._last = -1
        self._next_allowed = time.ticks_ms()
        self._revert_at = None
        self._reaction_face = None

    def set_enabled(self, enabled):
        self.enabled = enabled
        log("Touch interaction " + ("ON" if enabled else "OFF"))

    # ------------------------------------------------------------------
    def update(self):
        """Call this from the main loop as often as possible."""
        # Always read the sensor so stale touches never pile up.
        touched = self.robot.touch.pressed()
        now = time.ticks_ms()

        if touched and self.enabled and time.ticks_diff(now, self._next_allowed) >= 0:
            self._react()

        self._revert_face_if_due()

    # ------------------------------------------------------------------
    def _pick(self):
        index = random.randrange(len(REACTIONS))
        if index == self._last:                       # never repeat twice in a row
            index = (index + 1) % len(REACTIONS)
        self._last = index
        return REACTIONS[index]

    def _react(self):
        expression, movement, time_ms, count = self._pick()
        log("TOUCH -> %s / %s" % (expression, movement))

        self.robot.set_expression(expression)
        self._reaction_face = expression

        if movement and movement in self.robot.movement_names():
            try:
                self.robot.run_movement(movement, time_ms, count)
            except Exception as e:
                error("Touch movement failed: " + str(e))

        now = time.ticks_ms()
        self._revert_at = time.ticks_add(now, config.TOUCH_FACE_HOLD_MS)
        self._next_allowed = time.ticks_add(now, config.TOUCH_COOLDOWN_MS)

    def _revert_face_if_due(self):
        if self._revert_at is None:
            return
        if time.ticks_diff(time.ticks_ms(), self._revert_at) < 0:
            return
        self._revert_at = None
        # Only go back to Normal if nobody changed the face in the meantime
        # (for example from the web UI).
        if self.robot.expression == self._reaction_face:
            self.robot.set_expression(IDLE_EXPRESSION)
