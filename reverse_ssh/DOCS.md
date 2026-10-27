# Setup (English)

This experimental app needs Home Assistant OS with Supervisor and an SSH server
you control. It forwards TCP; it does not install a VPN, reverse proxy or TLS.
Encrypted-key passphrase prompts and password login are unsupported.

## 1. Prepare an SSH account

Use a dedicated account and a dedicated Ed25519 key, rather than a server
administration key. Generate it on a trusted computer:

```sh
ssh-keygen -t ed25519 -f ha_tunnel -C home-assistant-tunnel
```

For unattended startup, leave its passphrase empty. Keep `ha_tunnel` secret;
only `ha_tunnel.pub` belongs in the remote user's authorized_keys. Restrict
the account to forwarding with no shell/session access. For example, on a
current OpenSSH server, a dedicated sshd Match block can use:

```text
Match User ha-tunnel
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding remote
    GatewayPorts no
    PermitListen 127.0.0.1:18123
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    PermitTunnel no
    MaxSessions 0
```

This is an example, not a command to overwrite sshd_config. Verify support
with `sshd -t` before reloading sshd and retain an existing admin connection.
The account must remain usable for public-key authentication under your OS's
account policy. This app does not change the SSH server.

With `127.0.0.1`, only software on the SSH server can access the reverse port.
A reverse proxy on that server can use it. For direct access from VPN clients,
set `remote_bind_address` to the server's VPN IP; the server then needs
`GatewayPorts clientspecified` and a matching `PermitListen`. Restrict access
with the server firewall to the intended VPN clients. An all-interface bind
such as `0.0.0.0` may expose HA publicly; it is never the default.

## 2. Upload two files

Install the app, then open its app-specific folder through Samba or another
trusted file editor with app-config access. This is normally
`/app_configs/<repository-id>_reverse_ssh/`, or `local_reverse_ssh` for a local
installation. The repository ID is assigned by HA; do not guess its hash.
Inside the container this folder is mounted read-only at `/config`.

Copy these exact filenames into that folder:

- `id_ed25519`: your private key (`ha_tunnel`, renamed).
- `known_hosts`: a verified SSH host-key entry for the server.

Obtain the host key through a trusted server console. `ssh-keyscan` can collect
a candidate entry, but cannot authenticate it: compare its fingerprint with
the host fingerprint shown through a trusted channel before accepting it.
For nonstandard SSH ports, known_hosts must use `[host]:port`. The hostname/IP
must match `ssh_host`. Never disable host-key checking to suppress an error.
The app makes private runtime copies and normalizes Windows CRLF line endings.
Uploaded files are not changed. Restart the app after replacing either file.

Keep these files out of GitHub. App configuration and keys may be included in
HA backups; protect backups accordingly. Copy/paste into an options field is
intentionally not provided in this version.

## 3. Configure

| Option | Default | Meaning |
| --- | --- | --- |
| ssh_host | empty (required) | SSH server IP or DNS name, not a URL |
| ssh_port | 22 | SSH server port |
| ssh_user | ha-tunnel | Dedicated remote SSH account |
| remote_bind_address | 127.0.0.1 | IP on SSH server where reverse port listens |
| remote_port | 18123 | Unused TCP port on SSH server |
| target_host | homeassistant | Destination reachable from the app container |
| target_port | 8123 | HA HTTP or HTTPS TCP port |
| use_autossh | true | Use autossh with SSH keepalives (monitor port disabled) |

The SSH endpoint is the server's reachable public or private address;
it need not be the VPN-interface IP. `remote_bind_address` describes the
listener on that server and may be a different address.

The default tunnel is equivalent to
`ssh -N -T -R 127.0.0.1:18123:homeassistant:8123 ha-tunnel@SERVER` with
additional key, host-verification and keepalive options. IPv6 is supported.
`localhost` as target refers to the app container, not HA Core.

The launcher reconnects after its client exits, waiting 10 seconds between attempts.
SSH keepalives use 30 seconds and three missed replies. Autossh additionally
supervises its SSH child and uses its own retry/backoff timing internally;
the launcher's 10-second pause applies only when autossh itself exits.
No process check guarantees that HA's HTTP endpoint
is healthy. Authentication/host-key failures remain fail-closed and appear in
logs. Missing/invalid files and options stop startup.

## 4. Test without interrupting existing access

Choose a free remote test port and authorize it in PermitListen. Start the
app and, on the SSH server, run `curl -I http://127.0.0.1:18123/` (adapt TLS,
address and port). Verify login and WebSocket behavior through your actual
VPN/proxy path. Test an app restart, network interruption and recovery, and
both autossh modes. Only then retire the old standalone container. To roll
back, stop this app and start the original tunnel/container.

For a reverse proxy, retain HA authentication, TLS at the appropriate endpoint
and WebSocket support. Configure HA trusted proxies only if required by your
proxy topology; an SSH tunnel alone does not add HTTP proxy headers.

## Troubleshooting

- Permission denied: check account, public key, account policy and key permissions.
- Host verification failed: verify the server key and matching host/port entry.
- Remote forwarding failed: check port collision, PermitListen and bind policy.
- Connection refused at destination: check target_host, target_port and HA TLS.
- No files: check app-specific directory and exact filenames, not HA's main config.
- Container running but no access: inspect the server listener and complete path;
  startup logs only confirm a client process was started.

References: [HA app configuration](https://contributors.home-assistant.io/apps/reference/configuration/),
[OpenSSH sshd_config](https://man.openbsd.org/sshd_config),
[OpenSSH client](https://man.openbsd.org/ssh).
