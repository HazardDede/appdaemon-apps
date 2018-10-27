import attr
from enum import Enum

import appdaemon.plugins.hass.hassapi as hass

import utils


__VERSION__ = "0.1.0"


class Op(Enum):
    Below = "below"
    Above = "above"
    Equals = "equals"

    @classmethod
    def from_str(cls, candidate):
        if not isinstance(candidate, str):
            raise TypeError("Argument 'candidate' is expected to be a str")
        ops = {op.value: op for op in cls}
        val = ops.get(candidate)
        if not val:
            raise ValueError("Argument 'candidate' should be one of {}".format(ops))
        return val


@attr.s
class Light:
    entity = attr.ib(type=str)
    hass = attr.ib()

    @classmethod
    def from_config(cls, cfg, hass):
        return [cls(entity=item, hass=hass) for item in cfg['lights']]

    def turn_on(self):
        self.hass.log("Turning on {self.entity}".format(**locals()))
        self.hass.turn_on(entity_id=self.entity)

    def turn_off(self):
        self.hass.log("Turning off {self.entity}".format(**locals()))
        self.hass.turn_off(entity_id=self.entity)


@attr.s
class Motion:
    entity = attr.ib(type=str)
    hass = attr.ib()

    @classmethod
    def from_config(cls, cfg, hass):
        return [cls(entity=item, hass=hass) for item in cfg['motion']]

    def on_motion(self, callback):
        self.hass.listen_state(callback, self.entity, new="on")

    def on_motion_off(self, callback):
        self.hass.listen_state(callback, self.entity, old='on', new='off')


@attr.s
class Sensor:
    entity = attr.ib(type=str)
    op = attr.ib(type=str)
    value = attr.ib(type=(int, float))
    hass = attr.ib()

    @classmethod
    def from_config(cls, cfg, hass):
        return [cls(entity=item['entity'], op=item['op'], value=item['value'], hass=hass) for item in cfg['sensor']]

    def current(self):
        val = self.hass.get_state(entity=self.entity)
        return float(val) if val else None

    def is_within_limits(self):
        curval = self.current()
        if not curval:
            return False  # Device is unknown or error

        if self.op is Op.Below:
            res = curval < self.value
            self.hass.log("Limit check: {curval} < {self.value} = {res}".format(**locals()))
            return res
        if self.op is Op.Above:
            res = curval > self.value
            self.hass.log("Limit check: {curval} > {self.value} = {res}".format(**locals()))
            return res
        if self.op is Op.Equals:
            import math
            res = math.isclose(curval, self.value)
            self.hass.log("Limit check: {curval} > {self.value} = {res}".format(**locals()))
            return res
        return True


class Validator:
    from voluptuous import Schema, Required, Optional, Range, All, Or, And

    SENSOR_SCHEMA = Schema({
        Required("entity"): str,
        Required("op"): And(str, Op.from_str),
        Required("value"): Or(float, int)
    })

    SCHEMA = Schema({
        Optional("for", default="5m"): utils.parse_duration_literal,  # Lights on for x seconds
        Required("lights"): Or([str], lambda v: [v] if isinstance(v, str) else []),
        Required("motion"): Or([str], lambda v: [v] if isinstance(v, str) else []),
        Optional("sensor", default=[]): Or([SENSOR_SCHEMA], lambda v: [Validator.SENSOR_SCHEMA(v)])
    }, extra=True)

    @classmethod
    def validate(cls, dct):
        return cls.SCHEMA(dct)


class App(hass.Hass):
    def initialize(self):
        self.log("Motion App @ {version}".format(version=__VERSION__))
        cfg = Validator.validate(self.args)

        self._lights = Light.from_config(cfg, self)
        self._motion = Motion.from_config(cfg, self)
        self._sensor = Sensor.from_config(cfg, self)
        self._for = cfg['for']
        self._timer = None

        for motion in self._motion:
            motion.on_motion(self._on_motion)
            motion.on_motion_off(self._on_motion_off)

    def _on_motion(self, entity, attribute, old, new, kwargs):
        self.log("Motion detected @ {entity}: {old} -> {new}".format(**locals()))
        for sensor in self._sensor:
            if not sensor.is_within_limits():
                return
        for light in self._lights:
            light.turn_on()
        self._safe_cancel_timer()

    def _on_motion_off(self, entity, attribute, old, new, kwargs):
        self.log("Motion off @ {entity}: {old} -> {new}".format(**locals()))
        self._safe_cancel_timer()
        self._timer = self.run_in(self._on_turn_off_after_delay, self._for)

    def _on_turn_off_after_delay(self, kwargs):
        for light in self._lights:
            light.turn_off()

    def _safe_cancel_timer(self):
        if self._timer:
            self.cancel_timer(self._timer)
