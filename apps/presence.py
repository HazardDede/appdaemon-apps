from enum import Enum
import time

import appdaemon.plugins.hass.hassapi as hass

import utils


__VERSION__ = "0.3.0"


# Mapping
# Init the options of select_option
class State (Enum):
    Home = "home"
    JustArrived = "just_arrived"
    Away = "away"
    JustLeft = "just_left"
    ExtendedAway = "extended_away"

    @staticmethod
    def from_str(label):
        if not isinstance(label, str):
            raise TypeError("Argument 'label' is expected to be a str")
        if label.lower() in ('home'):
            return State.Home
        elif label.lower() in ('arrived', 'just arrived', 'just_arrived'):
            return State.JustArrived
        elif label.lower() in ('away', 'not_home'):
            return State.Away
        elif label.lower() in ('left', 'just left', 'just_left'):
            return State.JustLeft
        elif label.lower() in ('extended away', 'extended_away'):
            return State.ExtendedAway
        else:
            raise ValueError("Argument label '{label}' is expected to be valid state, but is not".format(**locals()))


class TrackerState(Enum):
    Home = "home"
    NotHome = "not_home"

    @staticmethod
    def from_str(label):
        if not isinstance(label, str):
            raise TypeError("Argument 'label' is expected to be a str")
        for s in TrackerState:
            if label == s.value:
                return s
        raise ValueError("Argument label '{label}' is expected to be valid state, but is not".format(**locals()))


class Validator:
    from voluptuous import Schema, Required, Optional, Range, All, Or

    T5_MINUTES = 5 * 60
    T24_HOURS = 24 * 60 * 60

    SCHEMA = Schema({
        Required('tracker'): str,
        Required('state'): str,
        Optional('map', default={state.value: state.value for state in State}): {state.value: str for state in State},
        Optional('just_left_delay', default=T5_MINUTES): utils.parse_duration_literal,
        Optional('just_arrived_delay', default=T5_MINUTES): utils.parse_duration_literal,
        Optional('extended_away_delay', default=T24_HOURS): utils.parse_duration_literal
    }, extra=True)

    @classmethod
    def validate(cls, dct):
        return cls.SCHEMA(dct)


class App(hass.Hass):
    def initialize(self):
        self.log("Presence App @ {version}".format(version=__VERSION__))

        cfg = Validator.validate(self.args)

        self._tracker_entity = cfg['tracker']
        self._state_entity = cfg['state']
        self._just_left_delay = cfg['just_left_delay']
        self._just_arrived_delay = cfg['just_arrived_delay']
        self._extended_away_delay = cfg['extended_away_delay']

        user_map = cfg['map']
        user_map = {State.from_str(k): v for k, v in user_map.items()}
        self._map = {state: user_map.get(state, state.value) for state in State}  # State to hass
        self._imap = {v: k for k, v in self._map.items()}  # hass to state

        self.timer = None
        self.current_state = None

        if cfg.get('init_options', False):
            self._set_options()
            time.sleep(1)  # We have to wait after setting the mode - otherwise the read is "wrong"

        self._init_current_state()

        self.listen_state(self._on_tracker_change, self._tracker_entity)

    def _on_tracker_change(self, entity, attribute, old, new, kwargs):
        self.log("On tracker change: {old} -> {new}".format(**locals()))
        old_state = TrackerState.from_str(old)
        new_state = TrackerState.from_str(new)
        if old_state == TrackerState.NotHome and new_state == TrackerState.Home:  # Mark person as just arrived
            if self._current_state is State.JustLeft:
                self._set_person_state(State.Home)  # Prevent oscillating when tracking was lost
            else:
                self._set_person_state(State.JustArrived)
        if old_state == TrackerState.Home and new_state == TrackerState.NotHome:  # Mark person as just left
            self._set_person_state(State.JustLeft)

    def _on_scheduled_state_change(self, kwargs):
        new_state = kwargs.pop('new_state')
        self._set_person_state(new_state)

    def _schedule_state_change(self, delay, new_state):
        self.timer = self.run_in(self._on_scheduled_state_change, delay, new_state=new_state)

    def _set_person_state(self, state):
        self.log("Calling input_select/select_option for {self._state_entity} with {state}".format(**locals()))
        self.call_service(
            "input_select/select_option",
            entity_id=self._state_entity,
            option=self._map[state]
        )
        self._current_state = state

        if self.timer:
            self.cancel_timer(self.timer)
        if state == State.JustArrived:
            self._schedule_state_change(self._just_arrived_delay, State.Home)  # Schedule Home in delay seconds
        elif state == State.JustLeft:
            self._schedule_state_change(self._just_left_delay, State.Away)  # Schedule Away in delay seconds
        elif state == State.Away:
            self._schedule_state_change(self._extended_away_delay, State.ExtendedAway)

    def _init_current_state(self):
        hass_state = self.get_state(entity=self._state_entity)
        self.log("Current state in hass is {hass_state}".format(**locals()))
        curstate = self._imap.get(hass_state)
        if curstate is None:
            self.log("Current state in hass is invalid. Falling back to {}".format(State.Home))
            curstate = State.Home
        tracker_state = TrackerState.from_str(self.get_state(entity=self._tracker_entity))
        if tracker_state is TrackerState.Home and curstate not in (State.JustArrived, State.Home):
            self.log("Current state '{curstate}' is invalid with tracker state '{tracker_state}'. "
                     "Resetting to home".format(**locals()))
            curstate = State.Home
        elif tracker_state is TrackerState.NotHome and curstate not in (State.JustLeft, State.Away, State.ExtendedAway):
            self.log("Current state '{curstate}' is invalid with tracker state '{tracker_state}'. "
                     "Resetting to away".format(**locals()))
            curstate = State.Away

        self._set_person_state(state=curstate)

    def _set_options(self):
        curstate = self.get_state(entity=self._state_entity)
        self.log("Current state is {curstate}".format(**locals()))
        options = list(self._map.values())
        self.log("Setting state options to {options}".format(**locals()))

        self.call_service(
            "input_select/set_options",
            entity_id=self._state_entity,
            options=options
        )

        if curstate not in options:
            # The previous state of the mode entity is not longer a valid one - fallback
            self.log("Previous state is not longer valid - reverting to state = home")
            curstate = self._map[State.Home]
        # Restore the previous state if possible
        self.log("Restoring state to {curstate}".format(**locals()))
        self._set_person_state(self._imap[curstate])
