# appdaemon-apps

AppDaemon Apps for home-assistant for my private hosted home assistent instance. Feel free to use the apps.

## Running a demo

Run the following commands (make sure that docker and docker-compose is installed) to startup a home assistent and a appdaemon instance for demo purpose.

```bash
docker-compose up -d && docker logs --tail=50 -f appdaemon
```

Enter `http://localhost:8123` to your favorite browser to access the home assistent demo application.

When you finished `Ctrl + C` out of the logs and run:

```bash
docker-compose down
```

## Running appdaemon

Just mount your personal `apps.yaml` and inject your home assistant url and api key. It is vital that the auth_provider `legacy_api_password` is activated, cause appdaemon only supports this one. See the `configuration.yaml` of hass inside the `compose` folder.

```bash
# Build the appdaemon image
make docker  # OR: make docker-arm for arm-based host systems

docker run --name appdaemon-apps \
      -e TZ=Europe/Berlin \
      -e HA_URL=http://hass:8123 \
      -e HA_KEY=<your_key> \
      -v /path/to/your/app_yaml/folder:/apps \
      <docker image name>
```

If hass itself is running as a container make sure to link it accordingly.
Hint: Have a look @ the `docker-compose.yaml` for further reference.

## Apps

### Climate

Simple scheduler for thermostats. Is controlled by four modes: `Comfort`, `Energy Saving`, `Frost protection` and `Off`. The first three are just names that will trigger different schedules when activated. `Off` means that the scheduler will be turned off.

A mode has a baseline temperature (the temperature that is active, when no schedule is running) and can have multiple schedules that will change the target temperature of the device for a well defined span of time.

```yaml
climate:
  module: climate
  class: App
  check_interval: 5m  # Checks the setpoints every interval. Adjust setpoints if necessary
  mode: 
    entity: input_select.heating_mode  # The mode selector in hass
    map:  # Map the internal modes to human readable ones
      Comfort: comfort
      Energy saving: energy
      Frost protection: frost
      "Off": "off"
    init_options: True  # Set the options of input_select.heating_mode
  rooms:
    bath_downstairs:  # Just a name
      # Creates a sensor that tracks the current target temperature configured for this room
      # Default name is: "<room_name>_setpoint"
      # Default unit of measurement is: °C
      setpoint_sensor:
      thermostats:
        - input_number.bath_heater  # One or many thermostats (input_number or climate)
      comfort:  # Mode comfort
        setpoint: 20  # Baseline
        schedule:  # Heat up the bathroom in the morning
          - start: "06:30"
            end: "09:30"
            weekdays: "1-5"  # Mon - Fri
            setpoint: 22
          - start: "08:30"  # ... but later on weekends
            end: "10:00"
            weekdays: "6,7"  # Sat - Sun
            setpoint: 22
      energy:  # Mode energy
        setpoint: 17
      frost:  # Mode frost
        setpoint: 8
    living:  # Another room
      setpoint_sensor:  
        name: living_setpoint  # Override name
        attributes:  # Override attributes as you like
          unit_of_measurement: "Grad"
          friendly_name: "Target Temp: Living room"
          icon: mdi:thermostat
      thermostats:
        - input_number.hallway_heater
        - entity: input_number.gallery_heater
          offset: 1  # Offset will effectively increase/decrease temperature (if target is 21 this will be set to 22)
      comfort:
        setpoint: 21
        schedule:  # Some energy savings in the nighttime
          - start: "00:00"
            end: "06:00"
            setpoint: 19
          - start: "06:00"  # Heat up when input_boolean 'run_schedule' evaluates to true ('on')
            end: "23:59"
            setpoint: 24
            constraints:
              - input_boolean.run_schedule
      energy:
        setpoint: 18
      frost:
        setpoint: 8
```

### Motion

Will turn on lights / switches (single or multiple) when motion (binary_sensor) was detected. Will turn off the lights again after a specified amount of time.
If a sensor is specified any contraints will be checked before turning on the lights.

```yaml
motion_lights:
  module: motion
  class: App
  for: 2m  # Turn off lights after 2 minutes
  motion: binary_sensor.motion  # Track this motion device for motion (list is also possible)
  lights: # Turn on / off those lights
    - light.light1
    - light.light2
  sensor: # Check those sensors for constraints
    - entity: sensor.lux_1
      op: below  # Possible: below, above, equals (so far only numeric)
      lux: 10
```

### Presence

The supported device_tracker from hass is quite binary: `home` or `not_home`. But I want to know if somebody just the left or just arrived or is staying away for quite some time. To realize this is what this app aims for.

If somebody transitions from `home` to `not_home` the person will be marked as `Just left`. After a defined amout of time the person will be marked as `Away`. If he stays `Away` long enough, the person will be marked as `Extended Away`. If the person transitions from `not_home` to `home` he will be marked as `Just Arrived` and after a defined amount of time (you can probably guess) he will be marked as `Home`.

Idea is taken from here: [https://philhawthorne.com/making-home-assistants-presence-detection-not-so-binary/](https://philhawthorne.com/making-home-assistants-presence-detection-not-so-binary/)

```yaml
paula_state:
  module: presence
  class: App
  tracker: device_tracker.paula  # The device tracker
  state: input_select.paula_state  # The input_select that will hold the extended state
  init_options: True  # Init the states of the input_select
  just_arrived_delay: 10m  # When to transit from 'Just Arrived' to 'Home
  just_left_delay: 10m  # When to transit from 'Just Left' to 'Away'
  extended_away_delay: 24h  # When to transit from 'Away' to 'Extended Away'
  map:  # Mapping the internal states to human friendly names for hass
    home: "Home"
    away: "Away"
    extended_away: "Extended Away"
    just_arrived: "Just arrived"
    just_left: "Just left"
```

## Changelog

* 0.3.0: Add `setpoint_sensor` to climate app to provide current room setpoint to hass
* 0.2.1: Adds contraints to climate app schedules
* 0.2.0: Making linter happy, pass duration in seconds as literals (e.g. 10m, 2d, ...)
* 0.1.0: First working version