FROM eclipse-mosquitto:2

COPY ./infra/mqtt/mosquitto.conf /mosquitto/config/mosquitto.conf
COPY ./infra/mqtt/passwordfile /mosquitto/config/passwordfile

RUN chown mosquitto:mosquitto /mosquitto/config/passwordfile \
    && chmod 600 /mosquitto/config/passwordfile
