FROM alpine:3.22
ARG BUILD_ARCH
ARG BUILD_VERSION=0.1.0
LABEL io.hass.name="Reverse SSH Tunnel" \
      io.hass.description="Reverse SSH tunnel with optional autossh" \
      io.hass.type="addon" \
      io.hass.version="${BUILD_VERSION}" \
      io.hass.arch="${BUILD_ARCH}"
RUN apk add --no-cache openssh-client autossh python3
COPY tunnel.py /opt/reverse-ssh/tunnel.py
CMD ["python3", "-u", "/opt/reverse-ssh/tunnel.py"]
