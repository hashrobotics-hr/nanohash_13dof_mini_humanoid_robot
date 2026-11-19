# nanoface.py
# NanoHash V3 - Cute Animated Facial Expressions
# ESP32-C3 SuperMini + 1.3" SH1106 OLED 128x64

import time
import math

TAU = getattr(math, "tau", math.pi * 2)


class NanoFace:
    W = 128
    H = 64

    # Eye centers -- widened from the original 39/89 to spread the face out
    # and use more of the panel's horizontal space. Everything that's
    # structurally attached to an eye (eyebrow, pupil, gasp/blush marks,
    # glasses lens, etc.) is positioned relative to these two values, so
    # changing them here re-spaces every expression consistently.
    EX_L = 32
    EX_R = 96

    EXPRESSIONS = (
        "Normal", "Blinking", "Happy", "Laughing",
        "Sad", "Angry", "Confused", "Surprised",
        "Sleepy", "Shock", "Wink", "Excited",
        "Love", "Thinking", "Confident", "Dizzy",
        "Bored", "Embarrassed", "Scared", "Proud", "Curious",
        "Talking"
    )

    def __init__(self, oled):
        self.oled = oled
        self.expression = "Normal"
        self.start = time.ticks_ms()
        self.last = self.start
        self.frame = 0

    def set_expression(self, expression):
        if expression not in self.EXPRESSIONS:
            return
        self.expression = expression
        self.start = time.ticks_ms()
        self.frame = 0
        self.oled.fill(0)
        self.oled.show()

    def _t(self):
        return time.ticks_diff(time.ticks_ms(), self.start)

    # ---------- primitives ----------
    def _line(self, x1, y1, x2, y2, color=1):
        self.oled.line(x1, y1, x2, y2, color)

    def _circle(self, x, y, r, fill=True, color=1):
        self.oled.ellipse(x, y, r, r, color, 1 if fill else 0)

    def _ellipse(self, x, y, rx, ry, fill=True, color=1):
        self.oled.ellipse(x, y, rx, ry, color, 1 if fill else 0)

    def _rect(self, x, y, w, h, fill=True, color=1):
        if fill:
            self.oled.fill_rect(x, y, w, h, color)
        else:
            self.oled.rect(x, y, w, h, color)

    def _poly(self, points, color=1):
        # Draws a closed outline through the points (framebuf has no
        # reliable filled-polygon primitive across MicroPython builds).
        n = len(points)
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            self._line(x1, y1, x2, y2, color)

    def _arc(self, cx, cy, rx, ry, a1, a2, width=1, color=1):
        px = py = None
        for i in range(25):
            a = a1 + (a2 - a1) * i / 24
            x = int(cx + math.cos(a) * rx)
            y = int(cy + math.sin(a) * ry)
            if px is not None:
                self._line(px, py, x, y, color)
                if width > 1:
                    self._line(px, py + 1, x, y + 1, color)
            px, py = x, y

    def _spiral(self, cx, cy, r_max, turns=2.2, rot=0.0, steps=22, color=1):
        px = py = None
        for i in range(steps + 1):
            frac = i / steps
            a = rot + frac * TAU * turns
            r = r_max * (1 - frac)
            x = int(cx + math.cos(a) * r)
            y = int(cy + math.sin(a) * r)
            if px is not None:
                self._line(px, py, x, y, color)
            px, py = x, y

    def _eye(self, cx, cy, rx=17, ry=21, px=0, py=0):
        self._ellipse(cx, cy, rx, ry)                                   # white eye
        pr_x, pr_y = max(4, rx // 3), max(6, ry // 3)
        self._ellipse(cx + px, cy + py, pr_x, pr_y, color=0)            # black pupil (cut in)
        self._circle(cx + px - pr_x // 2, cy + py - pr_y // 2, 2)       # white glint

    def _brow(self, x1, y1, x2, y2):
        self._line(x1, y1, x2, y2)
        self._line(x1, y1 + 1, x2, y2 + 1)

    def _smile(self, cx=64, cy=48, rx=15, ry=7):
        self._arc(cx, cy, rx, ry, 0.15, math.pi - 0.15)

    def _frown(self, cx=64, cy=48, rx=10, ry=5):
        self._arc(cx, cy, rx, ry, math.pi + 0.15, TAU - 0.15)

    def _heart(self, cx, cy, s=1):
        self._circle(cx - 5 * s, cy - 2 * s, 5 * s)
        self._circle(cx + 5 * s, cy - 2 * s, 5 * s)
        self._poly([
            (cx - 10 * s, cy),
            (cx + 10 * s, cy),
            (cx, cy + 12 * s)
        ])

    def _sparkle(self, x, y, s=1):
        self._line(x, y - 6 * s, x, y + 6 * s)
        self._line(x - 6 * s, y, x + 6 * s, y)
        self._line(x - 3 * s, y - 3 * s, x + 3 * s, y + 3 * s)
        self._line(x + 3 * s, y - 3 * s, x - 3 * s, y + 3 * s)

    def _star_eye(self, cx, cy):
        self._circle(cx, cy, 16)
        self._poly([
            (cx, cy - 9), (cx + 3, cy - 3), (cx + 9, cy),
            (cx + 3, cy + 3), (cx, cy + 9), (cx - 3, cy + 3),
            (cx - 9, cy), (cx - 3, cy - 3)
        ], color=0)  # carve the star into the circle so it reads as a sparkle

    def _question(self, y_off=0):
        self._arc(119, 29 + y_off, 7, 9, math.pi + 0.2, TAU - 0.2)
        self._line(119, 38 + y_off, 119, 44 + y_off)
        self._circle(119, 51 + y_off, 2)

    def _z(self, x, y, s=1):
        self._line(x, y, x + 8 * s, y)
        self._line(x + 8 * s, y, x, y + 7 * s)
        self._line(x, y + 7 * s, x + 8 * s, y + 7 * s)

    # ---------- expressions ----------
    def _normal(self):
        t = self._t()
        phase = (t // 900) % 4
        px = (0, 3, -2, 1)[phase]
        py = (0, -1, 1, 0)[phase]

        self._brow(22, 12, 36, 11)
        self._brow(92, 11, 106, 12)
        self._eye(32, 32, 15, 19, px, py)
        self._eye(96, 32, 15, 19, px, py)
        self._smile(64, 51, 9, 5)

    def _blinking(self):
        t = self._t() % 3000

        if t < 1900:
            self._eye(32, 32, 15, 19, 1, 0)
            self._eye(96, 32, 15, 19, 1, 0)
        elif t < 2020:
            self._arc(32, 34, 15, 7, 0.15, math.pi - 0.15)
            self._arc(96, 34, 15, 7, 0.15, math.pi - 0.15)
        elif t < 2140:
            self._line(18, 34, 46, 34)
            self._line(82, 34, 110, 34)
        elif t < 2260:
            self._arc(32, 34, 15, 7, 0.15, math.pi - 0.15)
            self._arc(96, 34, 15, 7, 0.15, math.pi - 0.15)
        else:
            self._eye(32, 32, 15, 19, -1, 0)
            self._eye(96, 32, 15, 19, -1, 0)

        self._brow(22, 12, 36, 11)
        self._brow(92, 11, 106, 12)
        self._smile(64, 51, 9, 5)

    def _happy(self):
        t = self._t()
        bounce = int(2 * math.sin(t / 180))

        self._brow(22, 12, 36, 10)
        self._brow(92, 10, 106, 12)

        self._arc(32, 34 + bounce, 17, 13, math.pi, TAU)
        self._arc(96, 34 + bounce, 17, 13, math.pi, TAU)
        self._arc(32, 34 + bounce, 14, 9, math.pi, TAU)
        self._arc(96, 34 + bounce, 14, 9, math.pi, TAU)

        self._arc(64, 48, 11, 6, 0.1, math.pi - 0.1)
        self._line(54, 49, 74, 49)

    def _laughing(self):
        t = self._t()
        bounce = int(2 * math.sin(t / 100))

        self._brow(21, 14, 36, 10)
        self._brow(92, 10, 107, 14)

        self._line(20, 26 + bounce, 35, 34 + bounce)
        self._line(35, 34 + bounce, 20, 38 + bounce)
        self._line(108, 26 + bounce, 93, 34 + bounce)
        self._line(93, 34 + bounce, 108, 38 + bounce)

        self._line(18, 43, 31, 43)
        self._line(97, 43, 110, 43)

        mouth_h = 7 + int(4 * abs(math.sin(t / 130)))
        self._ellipse(64, 49, 14, mouth_h)
        self._line(52, 46, 76, 46)

    def _sad(self):
        t = self._t()

        self._brow(21, 13, 36, 17)
        self._brow(92, 17, 107, 13)

        self._eye(32, 34, 15, 19, 2, 2)
        self._eye(96, 34, 15, 19, -2, 2)

        self._frown(64, 52, 8, 4)

        t2 = t % 2200
        if t2 >= 1100:
            fall = min(12, (t2 - 1100) // 90)
            self._ellipse(31, 51 + fall, 2, 4)
            self._ellipse(97, 51 + fall, 2, 4)

    def _angry(self):
        t = self._t()
        move = int(2 * math.sin(t / 160))

        self._brow(20 + move, 12, 38 + move, 22 + move)
        self._brow(108 + move, 12, 90 + move, 22 + move)

        self._ellipse(32 + move, 34, 16, 13)
        self._ellipse(96 + move, 34, 16, 13)
        self._ellipse(36 + move, 35, 5, 7, color=0)
        self._ellipse(92 + move, 35, 5, 7, color=0)

        self._line(52 + move, 52, 76 + move, 52)
        self._line(58 + move, 48, 58 + move, 52)
        self._line(64 + move, 48, 64 + move, 52)
        self._line(70 + move, 48, 70 + move, 52)

    def _confused(self):
        t = self._t()
        p1 = int(3 * math.sin(t / 300))
        p2 = int(3 * math.sin(t / 300 + 1.5))

        self._brow(21, 12, 36, 10)
        self._brow(92, 15, 107, 12)

        self._eye(32, 34, 15, 19, p1, 0)
        self._eye(96, 34, 15, 19, p2, 0)

        self._smile(64, 52, 7, 3)
        self._question(int(2 * math.sin(t / 250)))

    def _surprised(self):
        t = self._t()
        pulse = int(2 * math.sin(t / 130))

        self._brow(22, 9, 36, 7)
        self._brow(92, 7, 106, 9)

        self._ellipse(32, 32, 18 + pulse, 23 + pulse)
        self._ellipse(96, 32, 18 + pulse, 23 + pulse)
        self._circle(32, 32, 7, color=0)
        self._circle(96, 32, 7, color=0)
        self._circle(32, 31, 2)
        self._circle(96, 31, 2)

        self._circle(64, 53, 5 + abs(pulse), fill=False)

        self._line(17, 30, 9, 27)
        self._line(17, 35, 8, 35)
        self._line(111, 30, 119, 27)
        self._line(111, 35, 120, 35)

    def _sleepy(self):
        t = self._t()
        d = int(2 * math.sin(t / 500))

        self._brow(22, 13, 36, 14)
        self._brow(92, 14, 106, 13)

        self._arc(32, 35 + d, 15, 7, 0.05, math.pi - 0.05)
        self._arc(96, 35 + d, 15, 7, 0.05, math.pi - 0.05)

        self._line(21, 38 + d, 43, 38 + d)
        self._line(85, 38 + d, 107, 38 + d)

        self._frown(64, 51, 7, 3)

        # z / Z cycle: none -> small z -> small z + big Z -> repeat
        stage = (t // 500) % 3
        if stage >= 1:
            self._z(106, 26, 1)
        if stage >= 2:
            self._z(114, 14, 2)

    def _shock(self):
        t = self._t()
        pulse = int(2 * math.sin(t / 100))

        self._brow(23, 9, 36, 7)
        self._brow(92, 7, 105, 9)

        self._ellipse(32, 32, 18 + pulse, 23 + pulse)
        self._ellipse(96, 32, 18 + pulse, 23 + pulse)
        self._circle(32, 32, 6, color=0)
        self._circle(96, 32, 6, color=0)
        self._circle(32, 31, 2)
        self._circle(96, 31, 2)

        self._ellipse(64, 53, 6 + abs(pulse), 8 + abs(pulse), fill=False)

        self._line(16, 28, 9, 25)
        self._line(16, 35, 8, 35)
        self._line(112, 28, 119, 25)
        self._line(112, 35, 120, 35)

    def _wink(self):
        t = self._t() % 2600
        p_open = int(3 * math.sin(t / 400))  # idle look-around in the open eye

        self._brow(22, 12, 36, 11)
        self._brow(92, 11, 106, 12)

        # Right-hand eye (code x=EX_L) always open.
        # Left-hand eye (code x=EX_R) cycles through a blink -- closes, holds, reopens.
        # (EX_R maps to the physically-left eye on this panel's mirrored orientation.)
        self._eye(32, 33, 15, 19, p_open, 0)

        if t < 1600:
            self._eye(96, 33, 15, 19, 0, 0)
        elif t < 1720:
            self._arc(96, 34, 14, 7, 0.15, math.pi - 0.15)
        elif t < 2200:
            self._line(82, 34, 110, 34)
        elif t < 2320:
            self._arc(96, 34, 14, 7, 0.15, math.pi - 0.15)
        else:
            self._eye(96, 33, 15, 19, 0, 0)

        self._smile(64, 52, 8, 4)

    def _excited(self):
        t = self._t()
        pulse = int(2 * math.sin(t / 120))

        self._brow(22, 10, 36, 8)
        self._brow(92, 8, 106, 10)

        self._star_eye(32, 32 + pulse)
        self._star_eye(96, 32 + pulse)

        self._ellipse(64, 51, 11, 8)
        self._line(55, 48, 73, 48)

        self._sparkle(8, 33, 1)
        self._sparkle(121, 33, 1)

    def _love(self):
        t = self._t() % 1000
        if t < 100 or (300 <= t < 380):
            scale = 2
        else:
            scale = 1

        self._brow(23, 11, 36, 9)
        self._brow(92, 9, 105, 11)

        self._heart(32, 31, scale)
        self._heart(96, 31, scale)

        self._smile(64, 51, 10, 5)

    def _thinking(self):
        t = self._t()
        p = int(3 * math.sin(t / 400))

        self._brow(22, 12, 36, 10)
        self._brow(92, 10, 106, 12)

        self._eye(32, 32, 15, 19, 3 + p, -5)
        self._eye(96, 32, 15, 19, 3 + p, -5)

        self._frown(64, 52, 6, 3)

        b1 = int(2 * math.sin(t / 300))
        b2 = int(2 * math.sin(t / 300 + 1.2))
        self._circle(115, 14 + b1, 3, fill=False)
        self._circle(123, 7 + b2, 2, fill=False)

        self._line(46, 54, 53, 49)
        self._line(53, 49, 58, 54)
        self._line(53, 49, 56, 45)

    def _confident(self):
        t = self._t()
        b = int(2 * math.sin(t / 400))

        self._brow(22, 11, 36, 9)
        self._brow(92, 9, 106, 11)

        self._ellipse(32, 32, 17, 10)
        self._ellipse(96, 32, 17, 10)

        self._line(15, 25, 49, 25)
        self._line(79, 25, 113, 25)
        self._line(15, 26, 49, 26)
        self._line(79, 26, 113, 26)

        self._line(49, 25, 64, 32)
        self._line(79, 25, 64, 32)

        # shining glint sweeping right -> left across each lens, looping
        shine_frac = (t % 1400) / 1400
        for cx in (32, 96):
            sx = cx - 15 + int(shine_frac * 30)
            self._line(sx, 25, sx + 7, 39, color=0)
            self._line(sx + 2, 25, sx + 9, 39, color=0)

        self._smile(64, 50 + b, 10, 5)
        self._sparkle(120, 32, 1)

    def _dizzy(self):
        t = self._t()
        rot = (t / 700.0) % TAU

        self._brow(22, 10, 36, 8)
        self._brow(92, 8, 106, 10)

        self._circle(32, 32, 17, fill=False)
        self._circle(96, 32, 17, fill=False)
        self._spiral(32, 32, 13, turns=2.2, rot=rot)
        self._spiral(96, 32, 13, turns=2.2, rot=rot + math.pi)

        w = int(2 * math.sin(t / 200))
        self._line(53, 54 + w, 58, 51 - w)
        self._line(58, 51 - w, 64, 55 + w)
        self._line(64, 55 + w, 70, 51 - w)
        self._line(70, 51 - w, 75, 54 + w)

        self._sparkle(8, 48, 1)
        self._sparkle(120, 48, 1)

    def _bored(self):
        t = self._t()
        tilt = int(3 * math.sin(t / 2500))  # slow, occasional head-tilt

        self._brow(22, 13, 36, 13)
        self._brow(92, 13, 106, 13)

        ey1 = 32 + tilt
        ey2 = 32 - tilt
        self._eye(32, ey1, 15, 19, 0, 3)
        self._eye(96, ey2, 15, 19, 0, 3)
        # heavy eyelids drooped over the top of each eye
        self._rect(14, ey1 - 20, 36, 17, color=0)
        self._rect(78, ey2 - 20, 36, 17, color=0)

        self._line(54, 52, 74, 52)  # flat, unimpressed mouth

    def _embarrassed(self):
        t = self._t()
        dart = int(5 * math.sin(t / 220))  # quick nervous eye darting

        self._brow(23, 12, 36, 11)
        self._brow(92, 11, 105, 12)

        self._eye(32, 32, 15, 19, dart, 0)
        self._eye(96, 32, 15, 19, dart, 0)

        self._smile(64, 51, 7, 3)

        for i in range(3):
            o = i * 4
            self._line(11 + o, 44, 17 + o, 48)
            self._line(111 + o, 44, 117 + o, 48)

    def _scared(self):
        t = self._t()
        shake = int(2 * math.sin(t / 90))   # fast full-face jitter
        trem = int(2 * math.sin(t / 60))    # trembling mouth

        self._brow(20 + shake, 8, 36, 12)
        self._brow(108 + shake, 8, 92, 12)

        self._ellipse(32 + shake, 32, 16, 20)
        self._ellipse(96 + shake, 32, 16, 20)
        self._circle(32 + shake, 34, 3, color=0)
        self._circle(96 + shake, 34, 3, color=0)

        self._line(56 + shake, 52 + trem, 64 + shake, 48 - trem)
        self._line(64 + shake, 48 - trem, 72 + shake, 52 + trem)

    def _proud(self):
        t = self._t()
        b = int(2 * math.sin(t / 500))  # slow chest-puff breathing

        self._brow(20, 8, 38, 6)
        self._brow(90, 6, 108, 8)

        self._eye(32, 34, 15, 19, 0, 4)
        self._eye(96, 34, 15, 19, 0, 4)

        self._smile(64, 50 + b, 13, 7)

    def _curious(self):
        t = self._t()
        track = int(4 * math.sin(t / 500))  # eyes tracking side to side

        self._brow(22, 12, 36, 10)   # normal brow
        self._brow(92, 6, 106, 10)   # one eyebrow raised

        self._eye(32, 35, 15, 19, track, 0)
        self._eye(96, 29, 15, 19, track, 0)

        self._smile(64, 51, 7, 3)

    def _talking(self):
        t = self._t()
        bt = t % 3000  # same blink rhythm as Blinking
        phase = (t // 900) % 4
        px = (0, 3, -2, 1)[phase]
        py = (0, -1, 1, 0)[phase]

        self._brow(22, 12, 36, 11)
        self._brow(92, 11, 106, 12)

        # eyes: Normal's idle glance, with a periodic full blink like Blinking
        if bt < 1900 or bt >= 2260:
            self._eye(32, 32, 15, 19, px, py)
            self._eye(96, 32, 15, 19, px, py)
        elif bt < 2020:
            self._arc(32, 34, 15, 7, 0.15, math.pi - 0.15)
            self._arc(96, 34, 15, 7, 0.15, math.pi - 0.15)
        elif bt < 2140:
            self._line(18, 34, 46, 34)
            self._line(82, 34, 110, 34)
        else:
            self._arc(32, 34, 15, 7, 0.15, math.pi - 0.15)
            self._arc(96, 34, 15, 7, 0.15, math.pi - 0.15)

        # mouth: irregular open/close to mimic speech, driven by two
        # different-frequency sine waves so it doesn't look mechanically even
        mouth_h = 1 + int(6 * abs(math.sin(t / 90)) * abs(math.sin(t / 230)))
        if mouth_h <= 2:
            self._line(56, 52, 72, 52)
        else:
            self._ellipse(64, 52, 10, mouth_h)

    def update(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last) < 45:
            return
        self.last = now
        self.frame += 1
        self.oled.fill(0)

        fn = getattr(self, "_" + self.expression.lower())
        fn()

        self.oled.show()