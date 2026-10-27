# Changelog

## 0.1.0

- Initial experimental version with optional autossh and reconnect supervision.
- Strict host verification and read-only uploaded credentials.
- Configurable remote listener and HA destination, including IPv6.
- German and English configuration labels and documentation.
- Build definitions for amd64 and aarch64; HA validation still pending.
- Local builds and Linux unit tests passed for both architectures (ARM64
  under emulation); real amd64 tunnel/reconnect and fail-closed tests passed.
