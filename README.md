# Reverse SSH Tunnel for Home Assistant

Experimental Home Assistant app (formerly add-on), by up-quirk.
Create an outbound SSH connection to a server you control and forward a port
on that server back to Home Assistant. Works with Lightsail or any compatible
OpenSSH server; a VPN on that server is optional.

**Status:** experimental version 0.1.1. A real HA/OpenVPN/NAT deployment has
been manually verified; other VPN/routing setups still require their own tests.
Local amd64/arm64 builds, Linux unit tests and amd64 disposable-SSH-server
integration tests have passed; see the verification record below.
The Supervisor builds the image locally; no prebuilt container image is
published. Do not replace a working remote access path until the new connection
has been tested independently.

- Optional autossh; reconnects in either mode.
- Strict SSH host verification; uploaded key file, never embedded in the image.
- Configurable server, user, ports, remote bind IP and destination.
- amd64 and aarch64 build definitions; no privileged mode or host networking.
- MIT licensed. Not affiliated with Home Assistant or Nabu Casa.

[English setup](reverse_ssh/DOCS.md) · [Deutsche Anleitung](reverse_ssh/DOCS.de.md)

## Installation

Add `https://github.com/up-quirk/ha-reverse-ssh` as a repository in
Settings → Apps → Install app → menu → Repositories, then install
**Reverse SSH Tunnel**. The Supervisor builds the image locally.
For local development, copy only `reverse_ssh/` into the local apps folder
and refresh the store. Older HA releases call this folder `addons` and the
store Add-on Store; current releases use `local_apps` and Apps.

## Development

Python launcher has no third-party runtime dependencies.

```sh
python -m unittest discover -s tests -v
python -m pip install -r requirements-dev.txt
python tools/validate_metadata.py
docker build --build-arg BUILD_ARCH=amd64 -t ha-reverse-ssh:dev reverse_ssh
docker build -t ha-reverse-ssh-fixture:dev tests/integration
python tools/integration_test.py
```

GitHub CI runs tests, structural metadata validation and image builds for both
architectures. On amd64, it also runs the disposable-server integration test.
It creates an internal network with no published ports and new test-only SSH
keys in a temporary Docker volume, then removes its test containers, volume
and network in a finally block. Test images remain for build caching.
A passing build or disposable-server test is not an HA compatibility test.
See [local verification record](docs/VERIFICATION.md).

Only this repository's files belong in a public upload. Never add keys,
known_hosts containing personal server addresses, options.json or HA backups.
