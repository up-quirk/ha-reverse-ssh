# Reverse SSH app: approved design and implementation plan

Approved in chat on 2026-10-27. Local implementation and available tests only;
publishing and installation are separate steps. No existing HA state changes.

Architecture: Supervisor-managed Alpine container, OpenSSH and optional autossh.
A small Python launcher reads options, validates them, prepares private runtime
copies of the uploaded key and known_hosts, and supervises one foreground child.
No API access, Docker socket, host networking, public listener, or privileges.
The SSH server owns the reverse listener. Default bind address is loopback.

Configuration: ssh_host, ssh_port, ssh_user, remote_bind_address, remote_port,
target_host, target_port, use_autossh. Fixed key files in the app_config mount.
Strict host verification and noninteractive authentication are mandatory.
Encrypted keys requiring interactive passphrases are unsupported in v0.1.0.
Build locally on amd64 and aarch64; no published image dependency.

Execution checklist:
- [x] Write behavior tests for arguments, validation, credential handling,
      reconnection and termination; run before implementation.
- [x] Implement launcher and container/app metadata; run unit tests.
- [x] Write German/English setup, server restrictions and migration instructions.
- [x] Add GitHub CI for tests, metadata validation and both image builds.
- [x] Record actual local checks and outstanding HA/container checks.

Tests use unittest and temporary files, with a fake child only at the process
boundary. Linux-specific permission and signal checks run in Linux CI/container.
No private keys, personal HA files, generated credentials or actual hostnames
are part of this repository. MIT license. Initial release is experimental.
