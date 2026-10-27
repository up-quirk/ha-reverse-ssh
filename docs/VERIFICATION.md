# Local verification — 2026-10-27

Status: published experimental app. The original local-test record below is
historical; subsequent CI and user-reported HA deployment checks are recorded here.

## Version 0.1.2 local checks

- amd64 and aarch64 Docker builds succeeded. All 13 unit tests passed under
  Linux on both architectures (aarch64 under emulation); Windows passed with
  the privileged symlink test skipped. Metadata/YAML checks passed.
- Real isolated amd64 SSH-server tests passed: initial missing-file wait,
  clean stop during setup, automatic tunnel start after later file upload,
  HTTP forwarding in both SSH/autossh modes, reconnect after server restart,
  occupied-port rejection/recovery, wrong host-key rejection and encrypted-key rejection.
- Review found no blocking issues. Non-atomic uploads may expose a partial key;
  if key parsing fails, finish the upload and restart, as documented.
- Native configuration help is implemented as the SSH-host field description.
  Frontend source supports field descriptions but no custom app information box.
  No live HA upgrade or frontend-rendering test was performed for this version.

## Published and user-reported deployment checks — 2026-10-27

- Version 0.1.0 was published to up-quirk/ha-reverse-ssh. All 25 published files
  were compared with the local project (normalized line endings/final newlines).
- [First GitHub run](https://github.com/up-quirk/ha-reverse-ssh/actions/runs/40502414692)
  succeeded: unit/metadata tests, amd64/aarch64 builds and amd64 integration checks.
- The user installed the app on HA OS, configured it and populated its app_config
  folder after the first start attempt. A compatible existing PEM client key and
  a server public host key obtained through the server console were used.
- User-provided server output showed HTTP 200 through a separate test port.
- The user stopped the old standalone tunnel: phone access stopped. Starting the
  new app restored HA access through OpenVPN and an existing VPN-to-loopback NAT
  rule. This verifies the new app carried that route, not the old container.
- The server was observed listening on wildcard IPv4/IPv6 addresses with
  GatewayPorts yes. Restricting it to loopback was discussed, but has not been
  reported as performed. No claim of complete Internet isolation is made.
- Version 0.1.1 expands setup documentation/translations and changes release
  metadata only; tunnel.py is unchanged. Current automation results are under
  [GitHub Actions](https://github.com/up-quirk/ha-reverse-ssh/actions).

The deployment result is based on the user's pasted command outputs and manual
phone test. The agent did not connect to the real external server or inspect
private key contents. Other VPN topologies, full WebSocket/live-update behavior,
HA-host reboot recovery and backup/restore behavior remain separately unverified.

## Local Docker environment

Docker Desktop was updated from 4.49.0 to 4.97.0 through the official Docker
package in winget (installer checksum verified by winget). Following the
user-approved change from hypervisorlaunchtype Off to Auto and a Windows
restart, HypervisorPresent is True and Docker reports its engine as linux.
The local environment is now functional. No HA or Lightsail changes were made.

## Passed

- Python 3.14 on Windows: 11 unittest cases collected, 10 passed and one
  Linux-only symlink test skipped. Table-driven cases include multiple invalid
  configuration values and both invalid-key and key-check-timeout branches.
- Python 3.12 in the amd64 App image: all 11 tests passed, including Linux
  permissions and rejection of actual symlink credentials.
- Python 3.12 in the arm64 App image under Docker emulation: all 11 tests passed.
- Both image builds succeeded: ha-reverse-ssh:dev (linux/amd64) and
  ha-reverse-ssh:arm64-dev (linux/arm64), using Alpine 3.22, OpenSSH 10.0_p1-r10
  and autossh 1.4g-r3. The fixture image also built successfully.
- Coverage: SSH/optional autossh command construction, strict host identity,
  IPv6 forwarding, input validation, missing/empty credentials, Windows newline
  normalization, source-file preservation, reconnect, graceful child stop,
  forced kill/reap and prevention of connection after key rejection.
- `python tools/validate_metadata.py`: YAML syntax, required fields, matching
  option/schema/translation fields, example options and restricted permissions.
  This is a structural check, not the actual Supervisor validator.
- Independent code review: no confirmed critical defects. Addressed review
  findings about startup/shutdown test gaps and autossh retry documentation.
- Real local Docker integration tests passed against the disposable OpenSSH
  server with a deterministic HTTP target:
  - SSH and autossh: HTTP response through the reverse tunnel.
  - Both modes: private runtime key permissions 600.
  - Both modes: reconnect after SSH-server container restart.
  - Both modes: graceful docker stop with exit code 0.
  - Occupied remote port: forwarding rejected, then automatic recovery after
    the fixture restart releases the port.
  - Incorrect known_hosts key: host verification rejected, no HTTP forwarding.
  - Passphrase-protected private key: startup rejected with exit code 1,
    no HTTP forwarding.
- Test resources were removed by the harness; a subsequent Docker inventory
  confirmed no ha-rssh-test- containers, volumes or networks remained.
- During the original local-test stage, no GitHub write, real HA/Lightsail
  connection, personal key upload or existing-tunnel change was performed.

The first integration run exposed a test-fixture issue: reserving the recently
closed reverse port failed with address-in-use before the collision test began.
The fixture now sets SO_REUSEADDR. A fresh complete run passed all checks;
the application code did not need a change for this correction.

## Reproduce on this Windows workspace

```powershell
New-Item -ItemType Directory -Path .test-tmp -Force | Out-Null
$env:TMP = Join-Path (Get-Location) '.test-tmp'
$env:TEMP = $env:TMP
./.venv/Scripts/python.exe -m unittest discover -s tests -v
./.venv/Scripts/python.exe tools/validate_metadata.py
docker build --build-arg BUILD_ARCH=amd64 -t ha-reverse-ssh:dev reverse_ssh
docker build --platform linux/arm64 --build-arg BUILD_ARCH=aarch64 -t ha-reverse-ssh:arm64-dev reverse_ssh
docker build -t ha-reverse-ssh-fixture:dev tests/integration
./.venv/Scripts/python.exe -u tools/integration_test.py
```

The temporary directory override is needed in this restricted execution
environment. It is not needed in a normal Python environment or Linux CI.
PyYAML 6.0.3 was installed into the ignored local .venv for metadata checks.

## Not yet verified

- Full integration test on actual ARM64 hardware; only the image build and
  unit suite under emulation were run for ARM64.
- A silent network blackhole lasting through the SSH keepalive deadline;
  reconnect was tested with a real server restart, not this separate failure mode.
- HA internal DNS target (the user used a LAN-IP target), comprehensive AppArmor
  and UI-label validation, backup behavior, full login/WebSocket coverage and
  HA-host reboot recovery. Basic installation/start/stop, file mount and phone
  reachability were user-tested as described above.

The successful container tests and one user-reported HA route do not establish
compatibility with every VPN or server policy. Before a stable release, broaden
deployment coverage and verify login, WebSockets and recovery while retaining
an independent administrative access path.
