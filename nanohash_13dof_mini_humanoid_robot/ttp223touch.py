from machine import Pin
from time import sleep_ms

class TouchSensor:
    def __init__(self, pin, debounce_ms=30):
        self.pin = Pin(pin, Pin.IN)
        self.debounce_ms = debounce_ms
        self.last_state = self.pin.value()

    def is_touched(self):
        return self.pin.value() == 1

    def pressed(self):
        state = self.pin.value()

        if state != self.last_state:
            sleep_ms(self.debounce_ms)
            state = self.pin.value()

            if state != self.last_state:
                self.last_state = state

                if state == 1:
                    return True

        return False

    def released(self):
        state = self.pin.value()

        if state != self.last_state:
            sleep_ms(self.debounce_ms)
            state = self.pin.value()

            if state != self.last_state:
                self.last_state = state

                if state == 0:
                    return True

        return False