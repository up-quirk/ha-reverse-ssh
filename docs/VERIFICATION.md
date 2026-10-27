# Local verification — 2026-10-27

Status: experimental local development artifact, not published or installed.

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
- No GitHub write, real HA/Lightsail connection, personal key upload or
  existing-tunnel change was performed.

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

- GitHub CI execution: workflow prepared, not run. It builds both architectures
  and runs the disposable-server integration checks on amd64.
- Full integration test on actual ARM64 hardware; only the image build and
  unit suite under emulation were run for ARM64.
- A silent network blackhole lasting through the SSH keepalive deadline;
  reconnect was tested with a real server restart, not this separate failure mode.
- Supervisor install/start/stop, app_config mount, HA DNS resolution, AppArmor,
  UI labels, backup behavior, login and WebSockets through the actual VPN/proxy.

The successful local tunnel tests establish container behavior, not Supervisor
or end-to-end HA compatibility. Before a stable release, install experimentally
with a different remote port while retaining the original access path and
verify the actual HA/VPN/proxy route, login and WebSockets.
