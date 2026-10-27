# Changelog

## 0.1.2

- Keep the first start running while credential files are missing or empty;
  start the tunnel automatically after both files are supplied.
- Explain credential files and link the setup guide in native SSH-host field help
  (Home Assistant does not provide a custom configuration-page information box).
- Keep strict host verification and reject invalid/passphrase-protected keys.

## 0.1.1

- Expanded German and English beginner guides with ASCII topology diagrams,
  external VPN prerequisites, three access paths and setup/test/migration recipes.
- Explained first-start app_config folder creation, both credential file formats
  and the difference between client keys and server host keys.
- Corrected bind-address help: GatewayPorts yes can override a loopback request.
- Use GET for HA checks; document the expected HEAD/405 response.
- No tunnel runtime logic changes.

## 0.1.0

- Initial experimental version with optional autossh and reconnect supervision.
- Strict host verification and read-only uploaded credentials.
- Configurable remote listener and HA destination, including IPv6.
- German and English configuration labels and documentation.
- Build definitions for amd64 and aarch64; HA validation still pending.
- Local builds and Linux unit tests passed for both architectures (ARM64
  under emulation); real amd64 tunnel/reconnect and fail-closed tests passed.
