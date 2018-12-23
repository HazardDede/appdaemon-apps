import appdaemon.plugins.hass.hassapi as hass


__VERSION__ = "0.3.0"


class App(hass.Hass):
    def initialize(self):
        self.log("Setting up FRITZ!Box Guest Wifi app")

        import fritzconnection.fritzconnection as fc
        self.host = self.args.get('host', fc.FRITZ_IP_ADDRESS)
        self.port = self.args.get('port', fc.FRITZ_TCP_PORT)
        self.user = self.args.get('user', fc.FRITZ_USERNAME)
        self.password = self.args.get('password', None)
        self.service = self.args.get('service', 'WLANConfiguration:2')
        self.entity = self.args.get('entity', None)
        self.dry_run = self.args.get('dryrun', False)

        if not self.password:
            raise ValueError("Config parameter 'password' is missing. Cannot setup a connection to FRITZ!Box")

        if not self.entity:
            raise ValueError("Config parameter 'entity' is missing. Cannot setup a state listener")

        if not self.dry_run:
            self._connection = fc.FritzConnection(
                address=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )

        self.listen_state(self._on_state_change, self.entity)
        self.log("Finished setting up FRITZ!Box Guest Wifi app")
        current_state = self.get_state(self.entity)
        self._turn_on_off(current_state == 'on')

    def _on_state_change(self, entity, attribute, old, new, kwargs):
        self.log("State change detected @ {entity}: {old} -> {new}".format(**locals()))
        if old == 'off' and new == 'on':
            self._turn_on_off(True)
        if old == 'on' and new == 'off':
            self._turn_on_off(False)

    def _turn_on_off(self, turn_on):
        self.log("Turning FRITZ!Box Guest Wifi {}".format('On' if turn_on else 'Off'))

        from fritzconnection.fritzconnection import ServiceError, ActionError
        new_state = '1' if turn_on else '0'
        try:
            if not self.dry_run:
                self._connection.call_action(self.service, 'SetEnable', NewEnable=new_state)
        except ServiceError or ActionError:
            import traceback
            self.log(traceback.format_exception())
            self.log('Error when calling the Guest Wifi service on the FRITZ!Box')
