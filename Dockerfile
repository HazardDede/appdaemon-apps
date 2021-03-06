FROM python:3.5-slim-stretch

# Mount extra apps and app.yaml
# Will be copied to the correct path
VOLUME /apps

# Mount dashboard config files
# Will be copied to the correct path
VOLUME /dashboards

# API Url
EXPOSE 5000
# Dashboard Url
EXPOSE 5050

# Environment vars we can configure against
# But these are optional, so we won't define them now
#ENV API_KEY secret_key
#ENV HA_URL http://hass:8123
#ENV HA_TOKEN your_long_lived_access_token_from_hass
#ENV DASH_URL http://hass:5050
#ENV EXTRA_CMD -D DEBUG

# Copy appdaemon into image
RUN mkdir -p /appdaemon
WORKDIR /appdaemon

RUN apt-get update -yy && apt-get install -yy \
    libffi6 \
    libffi-dev

# RUN apt-get update -yy && apt-get install -yy \
#     python3-lxml \
#     libxslt-dev \
#     libxml2-dev \
#     zlib1g-dev

# Upgrades pip
RUN pip3 install pip --upgrade

# First copy th requirements and re-use any existing docker layer's
# so far no requirements changed...
COPY requirements.txt .

# Install deps
RUN pip3 install -r requirements.txt

COPY . .

# Start script
RUN chmod +x ./entrypoint.sh
CMD [ "./entrypoint.sh" ]