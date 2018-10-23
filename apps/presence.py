import appdaemon.plugins.hass.hassapi as hass

from enum import Enum

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


class App(hass.Hass):
  #initialize() function which will be called at startup and reload
  def initialize(self):
    self.log("Presence initialized")

    self._tracker_entity = self.args['tracker']
    self._state_entity = self.args['state']
    self._just_left_delay = int(self.args.get('just_left_delay', 5 * 60))
    self._just_arrived_delay = int(self.args.get('just_arrived_delay', 5 * 60))
    self._extended_away_delay = int(self.args.get('extended_away_delay', 24 * 60 * 60))
    
    user_map = self.args.get('map', {})
    user_map = {State.from_str(k): v for k, v in user_map.items()}
    self._map = {state: user_map.get(state, state.value) for state in State}
    self.timer = None

    self._set_options()
    self.listen_state(self._on_tracker_change, self._tracker_entity)

  def _on_tracker_change(self, entity, attribute, old, new, kwargs):
    self.log("On tracker change: {old} -> {new}".format(**locals()))
    old_state = TrackerState.from_str(old)
    new_state = TrackerState.from_str(new)
    if old_state == TrackerState.NotHome and new_state == TrackerState.Home:  # Mark person as just arrived
      self._set_person_state(State.JustArrived)
      self._schedule_state_change(self._just_arrived_delay, State.Home)  # Schedule Home in delay seconds
    if old_state == TrackerState.Home and new_state == TrackerState.NotHome:  # Mark person as just left
      self._set_person_state(State.JustLeft)
      self._schedule_state_change(self._just_left_delay, State.Away)  # Schedule Away in delay seconds

  def _on_scheduled_state_change(self, kwargs):
      new_state = kwargs.pop('new_state')
      self._set_person_state(new_state)
      if new_state == State.Away:
        self._schedule_state_change(self._extended_away_delay, State.ExtendedAway)

  def _schedule_state_change(self, delay, new_state):
    if self.timer:
      self.cancel_timer(self.timer)
    self.timer = self.run_in(self._on_scheduled_state_change, delay, new_state=new_state)

  def _set_person_state(self, state):
    self.log("Calling input_select/select_option for {self._state_entity} with {state}".format(**locals()))
    self.call_service(
        "input_select/select_option", 
        entity_id=self._state_entity, 
        option=self._map[state]
    )

  def _set_options(self):
    self.call_service(
      "input_select/set_options",
      entity_id=self._state_entity,
      options=list(self._map.values())
    )
