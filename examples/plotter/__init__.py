import logging
import math
import time

from pylgbst import MoveHub, ColorDistanceSensor, COLORS, COLOR_RED, COLOR_CYAN

BASE_SPEED = 0.75
FIELD_WIDTH = 1.2
MOTOR_RATIO = 1.15


class Plotter(MoveHub):
    def __init__(self, connection=None):
        super(Plotter, self).__init__(connection)
        self.xpos = 0
        self.ypos = 0
        self.is_tool_down = False
        self._marker_color = False

    def initialize(self):
        self._reset_caret()
        self.xpos = 0
        self.ypos = 0
        self.is_tool_down = False

    def _reset_caret(self):
        self.motor_A.timed(0.2, BASE_SPEED)
        self.color_distance_sensor.subscribe(self._on_distance, mode=ColorDistanceSensor.COLOR_DISTANCE_FLOAT,
                                             granularity=5)
        try:
            self.motor_A.constant(-BASE_SPEED)
            count = 0
            max_tries = 50
            while not self._marker_color and count < max_tries:
                time.sleep(5.0 / max_tries)
                count += 1
            logging.debug("Centering tries: %s", count)
            if count >= max_tries:
                raise RuntimeError("Failed to center caret")
        finally:
            self.motor_A.stop()
            self.color_distance_sensor.unsubscribe(self._on_distance)

        self.motor_A.timed(FIELD_WIDTH, BASE_SPEED)

    def _on_distance(self, color, distance):
        self._marker_color = None
        logging.debug("Color: %s, distance %s", COLORS[color], distance)
        if color in (COLOR_RED, COLOR_CYAN):
            if distance <= 3:
                self._marker_color = color

    def finalize(self):
        self.motor_AB.stop()
        self.motor_external.stop()
        if self.is_tool_down:
            self._tool_up()

    def _tool_down(self):
        self.motor_external.angled(270, 1)
        self.is_tool_down = True

    def _tool_up(self):
        self.motor_external.angled(-270, 1)
        self.is_tool_down = False

    def move(self, movx, movy):
        if self.is_tool_down:
            self._tool_up()
        self._transfer_to(movx, movy)

    def line(self, movx, movy):
        if not self.is_tool_down:
            self._tool_down()
        self._transfer_to(movx, movy)

    def _transfer_to(self, movx, movy):
        if self.xpos + movx < -FIELD_WIDTH:
            logging.warning("Invalid xpos: %s", self.xpos)
            movx += self.xpos - FIELD_WIDTH

        if self.xpos + movx > FIELD_WIDTH:
            logging.warning("Invalid xpos: %s", self.xpos)
            movx -= self.xpos - FIELD_WIDTH
            self.xpos -= self.xpos - FIELD_WIDTH

        if not movy and not movx:
            logging.warning("No movement, ignored")
            return

        self.xpos += movx
        self.ypos += movy

        length, speed_a, speed_b = self.calc_motor(movx, movy)

        self.motor_AB.timed(length, -speed_a * BASE_SPEED, -speed_b * BASE_SPEED)

        # time.sleep(0.5)

    @staticmethod
    def calc_motor(movx, movy):
        amovx = float(abs(movx))
        amovy = float(abs(movy))

        length = max(amovx, amovy)

        speed_a = (movx / float(amovx)) if amovx else 0.0
        speed_b = (movy / float(amovy)) if amovy else 0.0

        if amovx >= amovy * MOTOR_RATIO:
            speed_b = movy / amovx * MOTOR_RATIO
        else:
            speed_a = movx / amovy / MOTOR_RATIO

        logging.info("Motor: %s with %s/%s", length, speed_a, speed_b)
        assert -1 <= speed_a <= 1
        assert -1 <= speed_b <= 1

        return length, speed_a, speed_b

    def circle(self, radius):
        if not self.is_tool_down:
            self._tool_down()

        parts = int(2 * math.pi * radius * 7)
        dur = 0.025
        logging.info("Circle of radius %s, %s parts with %s time", radius, parts, dur)
        speeds = []
        for x in range(0, parts):
            speed_a = math.sin(x * 2.0 * math.pi / float(parts))
            speed_b = math.cos(x * 2.0 * math.pi / float(parts))
            speeds.append((speed_a, speed_b))
            logging.debug("A: %s, B: %s", speed_a, speed_b)
        speeds.append((0, 0))

        for speed_a, speed_b in speeds:
            self.motor_AB.constant(speed_a * BASE_SPEED, -speed_b * BASE_SPEED * MOTOR_RATIO)
            time.sleep(dur)

    def spiral(self, rounds, growth):
        if not self.is_tool_down:
            self._tool_down()

        dur = 0.00
        parts = 12
        speeds = []
        for r in range(0, rounds):
            logging.info("Round: %s", r)

            for x in range(0, parts):
                speed_a = math.sin(x * 2.0 * math.pi / float(parts))
                speed_b = math.cos(x * 2.0 * math.pi / float(parts))
                dur += growth
                speeds.append((speed_a, speed_b, dur))
                logging.debug("A: %s, B: %s", speed_a, speed_b)
        speeds.append((0, 0, 0))

        for speed_a, speed_b, dur in speeds:
            self.motor_AB.constant(speed_a * BASE_SPEED, -speed_b * BASE_SPEED * MOTOR_RATIO)
            time.sleep(dur)
