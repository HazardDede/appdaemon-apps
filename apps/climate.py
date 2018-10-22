import appdaemon.plugins.hass.hassapi as hass
import datetime
import logging

from enum import Enum

class Mode (Enum):
    Comfort = "comfort"
    EnergySaving = "energy"
    FrostProtection = "frost"

    @staticmethod
    def from_str(label):
        if label.lower() in ('comfort'):
            return Mode.Comfort
        elif label.lower() in ('energy', 'saving', 'energy saving'):
            return Mode.EnergySaving
        elif label.lower() in ('frost', 'protection', 'frost protection'):
            return Mode.FrostProtection
        else:
            raise NotImplementedError()

def str2time(candidate):
    def _eval(c):
        if not c:
            return 0
        return int(c)
    hour, _, minute = candidate.partition(":")
    if not hour and not minute:
        raise ValueError("Could not extract whether hour nor minute from schedule")
    return datetime.time(_eval(hour), _eval(minute), 0)


def validate_config(config):
    from voluptuous import Schema, Required, Optional, Range, All, Or
    
    setpoint_schema = Schema(All(Or(float, int), Range(min=0, max=28)))
    heating_schema = Schema({
        Required("setpoint"): setpoint_schema,
        Optional("schedule", default=[]): [{
            Required("start"): str2time,
            Required("end"): str2time,
            Required("setpoint"): setpoint_schema,
            Optional("weekdays"): str
        }]
    })
    
    schema = Schema({
        Required("mode"): {
            Required("entity"): str,
            Optional("map", default={}): {str: str}
        },
        Required("rooms"): {
            str: {
                Required("thermostats"): [str],
                Required("comfort"): heating_schema,
                Required("energy"): heating_schema,
                Required("frost"): heating_schema
            }
        }
    }, extra=True)
    return schema(config)


def is_time_between(begin_time, end_time, check_time=None):
    # If check time is not given, default to current UTC time
    check_time = check_time or datetime.datetime.now().time()
    if begin_time < end_time:
        return check_time >= begin_time and check_time <= end_time
    else: # crosses midnight
        return check_time >= begin_time or check_time <= end_time

def make_weekday_list(literal):
    if not literal: return list(range(1, 8))
    if isinstance(literal, int): return [literal]
    if isinstance(literal, (tuple, list)): return [int(i) for i in literal]
    if isinstance(literal, str):
        if '-' in literal:
            start, _, end = literal.partition('-')
            return list(range(int(start), int(end) + 1))
        if ',' in literal:
            return [int(i) for i in literal.split(',')]
        return [int(literal)]
    raise NotImplemented()


def eval_current_setpoint(config):
    default = config["setpoint"]
    wday = datetime.datetime.today().weekday() + 1
    schedules = config.get("schedule", [])
    if not schedules or len(schedules) == 0:
        return default
    
    for sched in schedules:
        start, end = sched["start"], sched["end"]
        weekdays = make_weekday_list(sched.get('weekdays'))
        if is_time_between(start, end) and wday in weekdays:
            return sched["setpoint"]

    return default

class Climate(hass.Hass):
    #initialize() function which will be called at startup and reload
    def initialize(self):
        cfg = validate_config(self.args)
        
        self._mode_entity = cfg["mode"]["entity"]
        self._mode_map = cfg["mode"]["map"]

        self._mode = self._resolve_mode(self.get_state(entity=self._mode_entity))
        self.log("Current mode is '{self._mode}'".format(**locals()))
        self.listen_state(self._on_mode_change, self._mode_entity)
        self.config = cfg
        self._update_setpoints_for_all_rooms()
        self._make_schedules()

        self.log("Climate controller initialized")
    
    def _make_schedules(self):
        for room, cfg in self.config["rooms"].items():
            for mode in Mode:
                for sched in cfg[mode.value].get("schedule", []):
                    start, end = sched["start"], sched["end"]
                    self.log("Creating schedule for room '{room}' @ {start} @ '{mode}'".format(**locals()))
                    self.run_daily(self._on_schedule, start, room=room, cfg=cfg)
                    self.log("Creating schedule for room '{room}' @ {end} @ '{mode}'".format(**locals()))
                    self.run_daily(self._on_schedule, end, room=room, cfg=cfg)
    
    def _resolve_mode(self, hass_mode):
        if self._mode_map:
            mode_label = self._mode_map.get(hass_mode, None)
            if not hass_mode:
                raise ValueError("State '{hass_mode}' is unknown to the mapping table".format(**locals()))
        return Mode.from_str(mode_label)

    def _update_setpoints_for_all_rooms(self):
        for room, cfg in self.config["rooms"].items():
            self._update_setpoints_for_room(room, cfg)

    def _on_schedule(self, kwargs):
        self.log("Scheduled change of setpoints for room '{room}'".format(room=kwargs.get('room')))
        self._update_setpoints_for_room(**kwargs)

    def _update_setpoints_for_room(self, room, cfg):
        schedule_config = cfg[self._mode.value]
        setpoint = eval_current_setpoint(schedule_config)
        self.log("Evaluated setpoint for '{room}' to '{setpoint}'".format(**locals()))
        self._set_thermostat_setpoint(cfg["thermostats"], setpoint)

    def _set_thermostat_setpoint(self, thermostats, setpoint):
        for t in thermostats:
            curval = self.get_state(entity=t)
            if curval != setpoint:
                self.log("Calling input_number/set_value for '{t}' with setpoint '{setpoint}'".format(**locals()))
                self.call_service(
                    "input_number/set_value", 
                    entity_id=t, 
                    value=setpoint
                )

    def _on_mode_change(self, entity, attribute, old, new, kwargs):
        self.log("Climate mode changed from '{old}' to '{new}'".format(**locals()))
        self._mode = self._resolve_mode(new)
        self.log("Resolved mode is: '{self._mode}'".format(**locals()))
        self._update_setpoints_for_all_rooms()
