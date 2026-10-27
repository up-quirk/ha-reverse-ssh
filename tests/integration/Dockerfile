FROM alpine:3.22
RUN apk add --no-cache openssh python3 \
    && adduser -D tunnel \
    && passwd -d tunnel
COPY server.py /test-server.py
CMD ["python3", "-u", "/test-server.py"]
