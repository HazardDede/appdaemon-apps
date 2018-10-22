#!/bin/sh

CONF=/appdaemon
VAPPS=/apps
VDASH=/dashboards

# if configuration file doesn't exist, fail
if [ ! -f $CONF/appdaemon.yaml ]; then
  echo "appdaemon.yaml does not exist. Exiting..."
  exit 1
fi

# if apps folder doesn't exist, fail
if [ ! -d $CONF/apps ]; then
  echo "app folder does not exist. Exiting..."
  exit 2
fi

echo "Copying app files from ${VAPPS} to ${CONF}/apps"
cp --verbose -rf ${VAPPS}/** ${CONF}/apps

# if apps file doesn't exist, fail
if [ ! -f $CONF/apps/apps.yaml ]; then
  # cp $CONF_SRC/apps/apps.yaml.example $CONF/apps/apps.yaml
  echo "apps.yaml does not exist. Exiting..."
  exit 3
fi

# if dashboards folder doesn't exist, fail
if [ ! -d $CONF/dashboards ]; then
  echo "dashboards folder does not exist. Exiting..."
  exit 4
fi

echo "Copying dashboard files from ${VDASH} to ${CONF}/dashboards"
cp --verbose -rf ${VDASH}/** ${CONF}/dashboards

# if ENV HA_URL is set, change the value in appdaemon.yaml
if [ -n "$API_KEY" ]; then
  sed -i "s/^  api_key:.*/  api_key: $(echo $API_KEY | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')/" $CONF/appdaemon.yaml
fi

# if ENV HA_URL is set, change the value in appdaemon.yaml
if [ -n "$HA_URL" ]; then
  sed -i "s/^      ha_url:.*/      ha_url: $(echo $HA_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')/" $CONF/appdaemon.yaml
fi

# if ENV HA_KEY is set, change the value in appdaemon.yaml
if [ -n "$HA_KEY" ]; then
  sed -i "s/^      ha_key:.*/      ha_key: $(echo $HA_KEY | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')/" $CONF/appdaemon.yaml
fi

# if ENV DASH_URL is set, change the value in appdaemon.yaml
if [ -n "$DASH_URL" ]; then
  if grep -q "^  dash_url" $CONF/appdaemon.yaml; then
    sed -i "s/^  dash_url:.*/  dash_url: $(echo $DASH_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')/" $CONF/appdaemon.yaml
  else
    sed -i "s/# Apps/HADashboard:\r\n  dash_url: $(echo $DASH_URL | sed -e 's/\\/\\\\/g; s/\//\\\//g; s/&/\\\&/g')\r\n# Apps/" $CONF/appdaemon.yaml
  fi
fi

# Lets run it!
exec appdaemon -c $CONF $EXTRA_CMD