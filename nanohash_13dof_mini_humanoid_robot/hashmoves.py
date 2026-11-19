from pca9685 import PCA9685
from machine import I2C, Pin
from servo import Servos
from time import sleep

# ---------------------------------------------------------------------------
# NanoHash joint map (measured from NanoHash_Final 3MF/STEP, +X = robot LEFT,
# front = -Y, up = +Z).  16 values per pose, in this order:
#   RL1,RL2,RL3, LL1,LL2,LL3, RH1,RH2,RH3, LH1,LH2,LH3, HEAD, DMY1,DMY2,DMY3
#
#  LEG  (same layout on both legs, servos are mirrored)
#   x3 = hip yaw   : vertical axis, in torso. toes turn left/right.
#   x2 = hip pitch : lateral axis, in the C-bracket. leg swings fwd/back.
#   x1 = ankle roll: front-back axis, in the foot. foot/body tilts sideways.
#   (there is NO ankle pitch and NO knee, so walking = ankle tilt + hip swing)
#
#  ARM  (same layout on both arms)
#   x3 = shoulder pitch : lateral axis in torso. arm swings fwd (rest = limit).
#   x2 = shoulder roll  : front-back axis. 0/180 = arm hanging, 90 = arm out
#                         sideways, 180/0 = arm straight up (right/left).
#   x1 = elbow          : lateral axis. hook hand swings fwd/back.
#
#  HEAD = yaw only (look left/right).
#
# Direction conventions (angle > 90 unless noted, servo turns CCW seen from
# its shaft tip):
#   RL1/LL1 > 90 : both ankles roll the same way -> body leans to robot RIGHT
#   RL2 > 90 : right foot swings BACK     LL2 > 90 : left foot swings FORWARD
#   RL3/LL3 > 90 : toes turn to robot RIGHT
#   RH3 up from 0 / LH3 down from 180 : arm swings FORWARD
#   RH2 up from 0 / LH2 down from 180 : arm raises sideways/up
#   HEAD > 90 : looks to robot LEFT
# If a motion runs mirrored on your hardware, flip the matching *_SIGN below.
# ---------------------------------------------------------------------------


class HashMoves:

    JOINTS = ["RL1", "RL2", "RL3", "LL1", "LL2", "LL3", "RH1", "RH2", "RH3",
              "LH1", "LH2", "LH3", "HEAD", "DMY1", "DMY2", "DMY3"]
    REST = [90, 90, 90, 90, 90, 90, 90, 0, 0, 90, 180, 180, 90, 0, 0, 0]

    # tuning values (degrees)
    LEAN = 18        # ankle tilt used to unload one foot
    STRIDE = 18      # hip swing for a step
    TURN = 25        # hip yaw for turning
    ARM_SWING = 35   # arm swing while walking
    LEAN_SIGN = 1    # -1 if the robot leans to the wrong side
    WALK_SIGN = 1    # -1 if "forward" walks backward
    TURN_SIGN = 1    # -1 if "turn left" turns right

    # walking gait (forward / backward) - hip swing is kept small so the
    # RL2/LL2 hip servos do not bend the legs too far
    WALK_STRIDE = 9  # hip swing each side of centre (leg moves 2x this per step)
    WALK_LEAN = 16   # ankle tilt used while walking
    WALK_ARM = 25    # arm swing while walking

    def initialize(self, i2c, servo=None):
        # Share the robot's Servos object so the web sliders and the
        # movements always agree on where each servo currently is.
        self.servo = servo if servo is not None else Servos(i2c=i2c)
        self.servo.initial_position()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _pose(self, **j):
        """16-angle list: rest pose with the named joints overridden."""
        a = list(self.REST)
        for k, v in j.items():
            a[self.JOINTS.index(k)] = max(0, min(180, int(v)))
        return a

    def _go(self, time, **j):
        self.servo.moveservo(time, self._pose(**j))

    def _rest(self, time):
        self.servo.moveservo(time, list(self.REST))

    def _lean(self, side, a=None):
        """Ankle angle: side=+1 leans right (left foot light), -1 leans left."""
        a = self.LEAN if a is None else a
        return 90 + self.LEAN_SIGN * side * a

    def _legs(self, s, side=0, lean=None):
        """Hip stride s>0: LEFT foot forward / RIGHT foot back (mirrored
        servos, so right = 90+s, left = 90+s). Includes ankle lean."""
        s = s * self.WALK_SIGN
        ank = self._lean(side, lean) if side else 90
        return dict(RL1=ank, LL1=ank, RL2=90 + s, LL2=90 + s)

    def _arms_walk(self, left_leg_forward, d=None):
        """Opposite arm swings forward with the forward leg."""
        d = self.ARM_SWING if d is None else d
        if left_leg_forward > 0:
            return dict(RH3=d, LH3=180)
        if left_leg_forward < 0:
            return dict(RH3=0, LH3=180 - d)
        return dict(RH3=0, LH3=180)

    # ------------------------------------------------------------------
    # walking: lean (unload a foot) -> swing that leg -> lean other way ...
    # ------------------------------------------------------------------
    def _walk(self, time, count, direction):
        s = self.WALK_STRIDE * direction
        lean = self.WALK_LEAN
        # 1) shift weight onto the right foot (left foot light), hips centred
        self._go(time, **self._legs(0, +1, lean))
        for x in range(count):
            # (hip sign, lean side): left foot light -> swing it, lean over to
            # the left, right foot light -> swing it, lean back ...
            for hs, side in ((+1, +1), (+1, -1), (-1, -1), (-1, +1)):
                p = self._legs(hs * s, side, lean)
                p.update(self._arms_walk(hs * direction * self.WALK_SIGN,
                                         self.WALK_ARM))
                self._go(time, **p)
        # finish: recentre the hips while still leaning, then stand level
        self._go(time, **self._legs(0, +1, lean))
        self._rest(time)

    def move_forward(self,time,count):
        self._walk(time, count, +1)

    def move_backward(self,time,count):
        self._walk(time, count, -1)

    # ------------------------------------------------------------------
    # turning on the spot (toes-turn in the air, plant, un-turn the planted
    # leg so the body rotates).  direction +1 = left, -1 = right
    # ------------------------------------------------------------------
    def _turn(self, time, count, direction):
        t = self.TURN * direction * self.TURN_SIGN   # + : toes to the left
        left_toes = 90 - t   # yaw angle that points toes LEFT is < 90
        right_toes = 90 - t
        for x in range(count):
            self._go(time, RL1=self._lean(+1), LL1=self._lean(+1),
                     LL3=left_toes, RL3=90)                       # left foot free
            self._go(time, RL1=self._lean(-1), LL1=self._lean(-1),
                     LL3=left_toes, RL3=90)                       # plant left
            self._go(time, RL1=self._lean(-1), LL1=self._lean(-1),
                     LL3=90, RL3=right_toes)                      # body turns
            self._go(time, RL1=self._lean(+1), LL1=self._lean(+1),
                     LL3=90, RL3=right_toes)                      # plant right
        self._go(time, RL1=self._lean(+1), LL1=self._lean(+1))
        self._rest(time)

    def turn_left(self,time,count):
        self._turn(time, count, +1)

    def turn_right(self,time,count):
        self._turn(time, count, -1)

    # ------------------------------------------------------------------
    # arms
    # ------------------------------------------------------------------
    def hands_up(self,time,count):
        self._go(time, RH2=180, LH2=0)

    def hands_down(self,time,count):
        self._rest(time)

    def t_pose(self,time,count):
        self._go(time, RH2=90, LH2=90)

    def hands_forward(self,time,count):
        self._go(time, RH3=80, LH3=100)

    def say_hi(self,time,count):
        # right arm raised outward, forearm waves
        self._go(time, RH2=130)
        for x in range(3):
            self._go(time/2, RH2=130, RH1=55)
            self._go(time/2, RH2=130, RH1=125)
        self._rest(time)

    def wave_left(self,time,count):
        self._go(time, LH2=50)
        for x in range(3):
            self._go(time/2, LH2=50, LH1=125)
            self._go(time/2, LH2=50, LH1=55)
        self._rest(time)

    def wave_both(self,time,count):
        self._go(time, RH2=130, LH2=50)
        for x in range(count + 2):
            self._go(time/2, RH2=130, LH2=50, RH1=55, LH1=125)
            self._go(time/2, RH2=130, LH2=50, RH1=125, LH1=55)
        self._rest(time)

    def hand_straight_shake(self,time,count):
        # handshake: right arm forward, elbow pumps
        self._go(time, RH3=70)
        for x in range(count):
            self._go(time/2, RH3=70, RH1=65)
            self._go(time/2, RH3=70, RH1=115)
        self._rest(time)

    def arms_flap(self,time,count):
        for x in range(count):
            self._go(time, RH2=130, LH2=50)
            self._go(time, RH2=40, LH2=140)
        self._rest(time)

    def cheer(self,time,count):
        self._go(time, RH2=180, LH2=0)
        for x in range(count):
            self._go(time/2, RH2=180, LH2=0, RH1=60, LH1=120,
                     RL1=self._lean(+1, 12), LL1=self._lean(+1, 12))
            self._go(time/2, RH2=180, LH2=0, RH1=120, LH1=60,
                     RL1=self._lean(-1, 12), LL1=self._lean(-1, 12))
        self._rest(time)

    # ------------------------------------------------------------------
    # head
    # ------------------------------------------------------------------
    def look_left(self,time,count):
        self._go(time, HEAD=135)

    def look_right(self,time,count):
        self._go(time, HEAD=45)

    def head_shake(self,time,count):
        for x in range(count):
            self._go(time/2, HEAD=125)
            self._go(time/2, HEAD=55)
        self._rest(time)

    def scan(self,time,count):
        for x in range(count):
            self._go(time, HEAD=140)
            self._go(time*2, HEAD=40)
        self._rest(time)

    def leg_head_shake(self,time,count):
        # hips twist one way while the head looks the other way
        for x in range(count):
            self._go(time, RL3=90 + self.TURN, LL3=90 + self.TURN, HEAD=45)
            self._go(time, RL3=90 - self.TURN, LL3=90 - self.TURN, HEAD=135)
        self._rest(time)

    # ------------------------------------------------------------------
    # side shuffle (feet drag sideways while leaning; small steps)
    # direction +1 = robot's right, -1 = left
    # ------------------------------------------------------------------
    def _side(self, time, count, direction):
        t = 20
        for x in range(count):
            # lean away from the travel side -> that foot is light, point toes
            self._go(time, RL1=self._lean(-direction), LL1=self._lean(-direction),
                     RL3=90 + t * direction, LL3=90 + t * direction)
            self._go(time, RL1=self._lean(direction), LL1=self._lean(direction),
                     RL3=90 + t * direction, LL3=90 + t * direction)
            self._go(time, RL1=self._lean(direction), LL1=self._lean(direction),
                     RL3=90, LL3=90)
            self._go(time, RL1=90, LL1=90)
        self._rest(time)

    def side_move_right(self,time,count):
        self._side(time, count, +1)

    def side_move_left(self,time,count):
        self._side(time, count, -1)

    # ------------------------------------------------------------------
    # legs / balance
    # ------------------------------------------------------------------
    def march(self,time,count):
        s = 22 * self.WALK_SIGN
        for x in range(count):
            self._go(time, RL1=self._lean(+1), LL1=self._lean(+1), LL2=90 + s,
                     RH3=self.ARM_SWING, LH3=180)
            self._go(time, RL1=self._lean(+1), LL1=self._lean(+1))
            self._go(time, RL1=self._lean(-1), LL1=self._lean(-1), RL2=90 + s,
                     RH3=0, LH3=180 - self.ARM_SWING)
            self._go(time, RL1=self._lean(-1), LL1=self._lean(-1))
        self._rest(time)

    def leg_shake(self,time,count):
        # stand on the right foot, shake the left leg, then the other one
        self._go(time, RL1=self._lean(+1, 22), LL1=self._lean(+1, 22))
        for x in range(count):
            self._go(time/2, RL1=self._lean(+1, 22), LL1=self._lean(+1, 22), LL2=90 + 25)
            self._go(time/2, RL1=self._lean(+1, 22), LL1=self._lean(+1, 22), LL2=90 - 15)
        self._go(time, RL1=self._lean(-1, 22), LL1=self._lean(-1, 22))
        for x in range(count):
            self._go(time/2, RL1=self._lean(-1, 22), LL1=self._lean(-1, 22), RL2=90 - 25)
            self._go(time/2, RL1=self._lean(-1, 22), LL1=self._lean(-1, 22), RL2=90 + 15)
        self._rest(time)

    def right_hand_balance(self,time,count):
        # arms out, stand on right foot, left leg forward
        self._go(time, RH2=90, LH2=90, RL1=self._lean(+1, 22), LL1=self._lean(+1, 22))
        self._go(time*2, RH2=90, LH2=90, RL1=self._lean(+1, 22),
                 LL1=self._lean(+1, 22), LL2=90 + 30)
        for x in range(count):
            self._go(time/2, RH2=100, LH2=80, RL1=self._lean(+1, 22),
                     LL1=self._lean(+1, 22), LL2=90 + 30)
            self._go(time/2, RH2=80, LH2=100, RL1=self._lean(+1, 22),
                     LL1=self._lean(+1, 22), LL2=90 + 30)
        self._rest(time*2)

    def left_hand_balance(self,time,count):
        self._go(time, RH2=90, LH2=90, RL1=self._lean(-1, 22), LL1=self._lean(-1, 22))
        self._go(time*2, RH2=90, LH2=90, RL1=self._lean(-1, 22),
                 LL1=self._lean(-1, 22), RL2=90 - 30)
        for x in range(count):
            self._go(time/2, RH2=100, LH2=80, RL1=self._lean(-1, 22),
                     LL1=self._lean(-1, 22), RL2=90 - 30)
            self._go(time/2, RH2=80, LH2=100, RL1=self._lean(-1, 22),
                     LL1=self._lean(-1, 22), RL2=90 - 30)
        self._rest(time*2)

    # ------------------------------------------------------------------
    # dance / fun
    # ------------------------------------------------------------------
    def side_shake(self,time,count):
        for x in range(count):
            self._go(time, RL1=self._lean(+1), LL1=self._lean(+1), RH2=40, LH2=170)
            self._go(time, RL1=self._lean(-1), LL1=self._lean(-1), RH2=10, LH2=140)

        self._rest(time)

    def right_slide_wave(self,time,count):
        self._go(time, RL1=self._lean(-1), LL1=self._lean(-1), RH2=130)
        for x in range(count):
            self._go(time/2, RL1=self._lean(-1), LL1=self._lean(-1), RH2=130, RH1=55, HEAD=60)
            self._go(time/2, RL1=self._lean(+1), LL1=self._lean(+1), RH2=130, RH1=125, HEAD=120)
        self._rest(time)

    def left_slide_wave(self,time,count):
        self._go(time, RL1=self._lean(+1), LL1=self._lean(+1), LH2=50)
        for x in range(count):
            self._go(time/2, RL1=self._lean(+1), LL1=self._lean(+1), LH2=50, LH1=125, HEAD=120)
            self._go(time/2, RL1=self._lean(-1), LL1=self._lean(-1), LH2=50, LH1=55, HEAD=60)
        self._rest(time)

    def twist(self,time,count):
        # planted feet, both hips turn the body left/right
        for x in range(count):
            self._go(time, RL3=90 + self.TURN, LL3=90 + self.TURN, RH2=60, LH2=120)
            self._go(time, RL3=90 - self.TURN, LL3=90 - self.TURN, RH2=20, LH2=160)
        self._rest(time)

    def flying_move(self,time,count):
        self._go(time*2, RH2=90, LH2=90)
        for x in range(count):
            self._go(time, RH2=130, LH2=50, RL1=self._lean(+1, 12), LL1=self._lean(+1, 12))
            self._go(time, RH2=50, LH2=130, RL1=self._lean(-1, 12), LL1=self._lean(-1, 12))
        self._rest(time*2)

    def jump(self,time,count):
        # no knees: quick ankle bounce with arms thrown up
        for x in range(count):
            self._go(time, RL1=self._lean(+1, 22), LL1=self._lean(+1, 22), RH2=150, LH2=30)
            self._go(time, RL1=self._lean(-1, 22), LL1=self._lean(-1, 22), RH2=150, LH2=30)
            self._go(time, RH2=0, LH2=180)
        self._rest(time)

    def dance(self,time,count):
        for x in range(count):
            self.side_shake(time, 1)
            self.twist(time, 1)
            self.arms_flap(time, 1)
            self.head_shake(time, 1)
            self.march(time, 1)
        self._rest(time)