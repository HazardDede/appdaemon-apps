import attr
import datetime
from enum import Enum
import time

import appdaemon.plugins.hass.hassapi as hass

import utils


__VERSION__ = "0.2.0"
MIN_TEMP = 8
MAX_TEMP = 28


class Mode (Enum):
    Comfort = "comfort"
    EnergySaving = "energy"
    FrostProtection = "frost"
    Off = "off"

    @staticmethod
    def from_str(label):
        if not isinstance(label, str):
            raise TypeError("Argument 'label' is expected to be a str")
        if label.lower() in ('comfort'):
            return Mode.Comfort
        elif label.lower() in ('energy', 'saving', 'energy saving'):
            return Mode.EnergySaving
        elif label.lower() in ('frost', 'protection', 'frost protection'):
            return Mode.FrostProtection
        elif label.lower() in ('off'):
            return Mode.Off
        else:
            raise ValueError("Argument label '{label}' is expected to be valid mode, but is not".format(**locals()))


@attr.s
class Thermostat:
    name = attr.ib(type=str)
    offset = attr.ib(type=(int, float), default=0)

    def set_setpoint(self, hass, setpoint):
        raise NotImplementedError()

    @classmethod
    def _factory(cls, tht):
        entity = tht
        offset = 0
        if isinstance(tht, dict):  # Complex with offset
            entity = tht['entity']
            offset = tht['offset']
        if entity.startswith("input_number"):
            return InputNumberThermostat(name=entity, offset=offset)
        if entity.startswith("climate"):
            return ClimateThermostat(name=entity, offset=offset)
        raise NotImplementedError("Sorry but the thermostat '{}' you provided is not supported".format(**locals()))

    @classmethod
    def from_dict(cls, dct):
        return [cls._factory(tht) for tht in dct]


@attr.s
class InputNumberThermostat(Thermostat):
    def set_setpoint(self, hass, setpoint):
        curval = hass.get_state(entity=self.name)
        offsetted_sp = setpoint + self.offset
        range_sp = min(max(MIN_TEMP, int(offsetted_sp + 0.5)), MAX_TEMP)  # Min, Max + Rounding
        import math
        if not math.isclose(float(curval), float(range_sp)):
            hass.log("Calling input_number/set_value for '{self.name}' with setpoint "
                     "'{range_sp}' (offset='{self.offset}')".format(**locals()))
            hass.call_service(
                "input_number/set_value",
                entity_id=self.name,
                value=range_sp
            )


@attr.s
class ClimateThermostat(Thermostat):
    def set_setpoint(self, hass, setpoint):
        curval = hass.get_state(entity=self.name, attribute="temperature")
        offsetted_sp = setpoint + self.offset
        range_sp = min(max(MIN_TEMP, int(offsetted_sp + 0.5)), MAX_TEMP)  # Min, Max + Rounding
        import math
        if not math.isclose(float(curval), float(range_sp)):
            hass.log("Calling climate/set_temperature for '{self.name}' with setpoint "
                     "'{range_sp}' (offset='{self.offset}')".format(**locals()))
            hass.call_service(
                "climate/set_temperature",
                entity_id=self.name,
                temperature=range_sp
            )


@attr.s
class BinarySensor:
    entity = attr.ib(type=str)

    @classmethod
    def from_config(cls, cfg):
        return [cls(entity=item) for item in cfg]

    def current(self, hass):
        val = hass.get_state(entity=self.entity)
        return str(val.lower()) in ['on', 'true', 'home']

    def on_change(self, hass, callback, room):
        return hass.listen_state(callback, self.entity, room=room)


@attr.s
class Schedule:
    setpoint = attr.ib(type=(float, int))
    start = attr.ib(type=datetime.time)
    end = attr.ib(type=datetime.time)
    weekdays = attr.ib(type=(list, None))
    constraints = attr.ib(type=list)

    @staticmethod
    def _make_weekday_list(literal):
        if not literal:
            return list(range(1, 8))
        if isinstance(literal, int):
            return [literal]
        if isinstance(literal, (tuple, list)):
            return [int(i) for i in literal]
        if isinstance(literal, str):
            if '-' in literal:
                start, _, end = literal.partition('-')
                return list(range(int(start), int(end) + 1))
            if ',' in literal:
                return [int(i) for i in literal.split(',')]
            return [int(literal)]
        raise NotImplementedError()

    @classmethod
    def from_dict(cls, dct):
        return [cls(
            setpoint=sched["setpoint"],
            start=sched["start"],
            end=sched["end"],
            weekdays=cls._make_weekday_list(sched.get("weekdays")),
            constraints=BinarySensor.from_config(sched.get("constraints", []))
        ) for sched in dct]


@attr.s
class Control:
    setpoint = attr.ib(type=(float, int))
    schedules = attr.ib(type=(list))

    @classmethod
    def from_dict(cls, dct):
        return cls(setpoint=dct["setpoint"], schedules=Schedule.from_dict(dct.get("schedule", [])))


@attr.s
class Room:
    name = attr.ib(type=str)
    thermostats = attr.ib(type=list)
    controls = attr.ib(type=dict)

    @classmethod
    def from_dict(cls, dct):
        return [cls(
            name=rname,
            thermostats=Thermostat.from_dict(rdct["thermostats"]),
            controls={mode: Control.from_dict(rdct[mode.value]) for mode in Mode if mode is not Mode.Off}
        ) for rname, rdct in dct.items()]

    @staticmethod
    def _is_time_between(begin_time, end_time, check_time=None):
        # If check time is not given, default to current UTC time
        check_time = check_time or datetime.datetime.now().time()
        if begin_time < end_time:
            return check_time >= begin_time and check_time <= end_time
        else:  # crosses midnight
            return check_time >= begin_time or check_time <= end_time

    def eval_setpoint(self, mode, hass, dt_override=None):
        if mode is Mode.Off:
            return None
        dt = dt_override or datetime.datetime.now()
        wday = dt.weekday() + 1
        ctrl = self.controls.get(mode)
        if not ctrl:
            raise ValueError("Given mode '{mode}' is not a control mode".format(**locals()))
        for sched in ctrl.schedules:
            start, end = sched.start, sched.end
            check_time = self._is_time_between(start, end, check_time=dt.time())
            check_weekdays = wday in sched.weekdays
            check_constraints = all([c.current(hass) for c in sched.constraints])
            if check_time and check_weekdays and check_constraints:
                return sched.setpoint
        return ctrl.setpoint  # Default setpoint when no schedule matches

    def update_setpoints(self, hass, mode, dt_override=None):
        if mode is Mode.Off:
            return
        setpoint = self.eval_setpoint(mode, hass, dt_override)
        hass.log("Evaluated setpoint for '{self.name}' to '{setpoint}'".format(**locals()))
        for tht in self.thermostats:
            tht.set_setpoint(hass, setpoint)


@attr.s
class Config:
    mode_entity = attr.ib(type=str)
    mode_map = attr.ib(type=dict)
    mode_init_options = attr.ib(type=bool)
    check_interval = attr.ib(type=int)
    rooms = attr.ib(type=list)

    @classmethod
    def from_dict(cls, dct):
        mode_node = dct["mode"]
        rooms_node = dct["rooms"]
        return cls(
            mode_entity=mode_node["entity"],
            mode_map=mode_node.get("map"),
            mode_init_options=mode_node.get("init_options", False),
            check_interval=dct["check_interval"],
            rooms=Room.from_dict(rooms_node)
        )


class Validator:
    from voluptuous import Schema, Required, Optional, Range, All, Or

    def str2time(candidate):
        def _eval(c):
            if not c:
                return 0
            return int(c)
        hour, _, minute = candidate.partition(":")
        if not hour and not minute:
            raise ValueError("Could not extract whether hour nor minute from schedule")
        return datetime.time(_eval(hour), _eval(minute), 0)

    SETPOINT_SCHEMA = Schema(All(Or(float, int), Range(min=MIN_TEMP, max=MAX_TEMP)))

    HEATING_SCHEMA = Schema({
        Required("setpoint"): SETPOINT_SCHEMA,
        Optional("schedule", default=[]): [{
            Required("start"): str2time,
            Required("end"): str2time,
            Required("setpoint"): SETPOINT_SCHEMA,
            Optional("weekdays"): str,
            Optional("constraints"): Or([str], lambda v: [v] if isinstance(v, str) else [])
        }]
    })

    THERMOSTAT_SCHEMA = Schema(Or(
        str,
        {
            Required("entity"): str,
            Optional("offset", default=0): int
        }
    ))

    SCHEMA = Schema({
        Optional("check_interval", default=0): utils.parse_duration_literal,
        Required("mode"): {
            Required("entity"): str,
            Optional("map", default={}): {str: str},
            Optional("init_options", default=False): bool
        },
        Required("rooms"): {
            str: {
                Required("thermostats"): [THERMOSTAT_SCHEMA],
                Required("comfort"): HEATING_SCHEMA,
                Required("energy"): HEATING_SCHEMA,
                Required("frost"): HEATING_SCHEMA
            }
        }
    }, extra=True)

    @classmethod
    def validate_config(cls, config):
        return cls.SCHEMA(config)


class App(hass.Hass):
    def initialize(self):
        self.log("Climate App @ {version}".format(version=__VERSION__))
        dct = Validator.validate_config(self.args)
        self._config = Config.from_dict(dct)
        self.schedules = []
        self.on_change_handler = []

        if self._config.mode_init_options:
            self._set_options()
            time.sleep(0.5)  # We have to wait after setting the mode - otherwise the read is "wrong"
        self._mode = self._resolve_mode(self.get_state(entity=self._config.mode_entity))
        self.log("Current mode is '{self._mode}'".format(**locals()))
        self.listen_state(self._on_mode_change, self._config.mode_entity)

        self._update_setpoints_for_all_rooms()
        self._make_schedules()
        if self._config.check_interval > 0:
            # Run every x `check_interval` seconds and set thermostats to reflect the current configuration
            self.run_every(
                self._on_interval,
                datetime.datetime.now() + datetime.timedelta(seconds=self._config.check_interval),
                self._config.check_interval
            )
        self.log("Climate controller initialized")

    def _on_schedule(self, kwargs):
        self.log("Scheduled change of setpoints for room '{room.name}'".format(room=kwargs.get('room')))
        kwargs['room'].update_setpoints(hass=self, mode=self._mode)

    def _on_interval(self, kwargs):
        self.log("On interval")
        self._update_setpoints_for_all_rooms()

    def _on_mode_change(self, entity, attribute, old, new, kwargs):
        self.log("Climate mode changed from '{old}' to '{new}'".format(**locals()))
        self._mode = self._resolve_mode(new)
        self.log("Resolved mode is: '{self._mode}'".format(**locals()))
        self._update_setpoints_for_all_rooms()
        self._make_schedules()

    def _on_constraint_change(self, entity, attribute, old, new, kwargs):
        self.log("Constraint '{entity}' value change from '{old}' to '{new}'".format(**locals()))
        room = kwargs.pop("room")
        room.update_setpoints(hass=self, mode=self._mode)

    def _resolve_mode(self, hass_mode):
        mode_label = hass_mode
        if self._config.mode_map:
            # If mapping key does not exist, use the original value
            mode_label = self._config.mode_map.get(hass_mode, hass_mode)
        return Mode.from_str(mode_label)

    def _make_schedules(self):
        # Remove old schedules if any
        self.log("Clearing current schedules")
        for handle in self.schedules:
            self.cancel_timer(handle)
        self.schedules.clear()

        # Remove contraints state change handler
        self.log("Clearing on_change event handler")
        for handle in self.on_change_handler:
            self.cancel_listen_state(handle)
        self.on_change_handler.clear()

        # New schedules
        mode = self._mode
        if mode is Mode.Off:
            return
        for room in self._config.rooms:
            for sched in room.controls[mode].schedules:
                start, end = sched.start, sched.end
                self.log("Creating schedule for room '{room.name}' @ {start} @ '{mode}'".format(**locals()))
                self.schedules.append(self.run_daily(self._on_schedule, start, room=room))
                self.log("Creating schedule for room '{room.name}' @ {end} @ '{mode}'".format(**locals()))
                self.schedules.append(self.run_daily(self._on_schedule, end, room=room))
                for c in sched.constraints:
                    self.log("Creating constraint on change handler for {c.entity} @ {room.name}".format(**locals()))
                    self.on_change_handler.append(c.on_change(self, self._on_constraint_change, room))

    def _update_setpoints_for_all_rooms(self):
        for room in self._config.rooms:
            room.update_setpoints(hass=self, mode=self._mode)

    def _set_options(self):
        # Memorize current state. set_options will revert the selection
        curstate = self.get_state(entity=self._config.mode_entity)
        self.log("Current mode is {curstate}".format(**locals()))

        invert_map = {mode: mode.value for mode in Mode}
        invert_map.update({Mode.from_str(v): k for k, v in self._config.mode_map.items()})
        options = [invert_map.get(mode, mode.value) for mode in Mode]
        self.log("Setting mode options to {options}".format(**locals()))
        self.call_service(
            "input_select/set_options",
            entity_id=self._config.mode_entity,
            options=options
        )

        if curstate not in options:
            # The previous state of the mode entity is not longer a valid one - fallback
            self.log("Previous mode is not longer valid - reverting to mode = off")
            curstate = invert_map[Mode.Off]
        # Restore the previous state if possible
        self.log("Restoring mode to {curstate}".format(**locals()))
        self.call_service("input_select/select_option", entity_id=self._config.mode_entity, option=curstate)


Climate = App  # Backwards compat
