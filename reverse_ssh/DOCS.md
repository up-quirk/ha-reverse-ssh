# Reverse SSH Tunnel: step-by-step setup

This app (formerly add-on) connects HA to your own external SSH server. A port
on that server leads back to HA through the tunnel. A VPN can restrict access
to your devices. The app installs neither a VPN nor a reverse proxy and does
not change the external server configuration.

## 1. Understand the components

```text
AT HOME                        EXTERNAL SERVER                  AWAY
HA OS                          VPS / e.g. Lightsail             phone / PC
+-------------------+          +----------------------+       +------------+
| Reverse SSH app   |-- SSH --->| SSH service :22      |       | VPN client |
| connects outward |          |                      |<==VPN==|            |
|                   |          | VPN service          |       +------------+
| HA Core :8123    |<--tunnel--| tunnel port :18123   |<-- request from VPN
+-------------------+          +----------------------+
```

SSH and VPN are **two separate connections**. The app connects from home to
the SSH service. Your phone connects to the VPN service. The external server
joins these access paths. Normally no incoming home-router port forwarding
is needed. HA still requires its own login.

All values below are **replaceable examples**, not ready-to-use credentials:

| Meaning | Example |
| --- | --- |
| Public SSH endpoint | `203.0.113.10` (documentation-only address: replace it!) |
| SSH port / dedicated tunnel user | `22` / `ha-tunnel` |
| VPN interface / server VPN IP | `tun0` / `10.8.0.1` |
| VPN client subnet | `10.8.0.0/24` |
| External tunnel port | `18123` |
| HA destination from app | `homeassistant:8123` |
| Familiar HA address for option B | `192.168.50.10:8123` |

Server port 18123 and HA port 8123 need not match. The app opens no new incoming
port on the HA host. Loopback (`127.0.0.1`) always refers to the current machine
or container, not automatically to Home Assistant.

## 2. Prepare the external VPN

You need a functioning, authenticated VPN to the external server, such as
OpenVPN or WireGuard. Install it using your VPN product's instructions with
your own certificates/keys and client profiles. This app does not replace that
installation or provide a complete VPN/PKI configuration.

1. Set up the VPN server and import your own client profile on the phone.
2. Allow the actual VPN port through cloud and server firewalls, often UDP
   1194 for OpenVPN. Your installation may use a different port/protocol.
3. Make the SSH service reachable from the HA site, usually on TCP 22.
4. Connect the phone to the VPN. Ensure the server VPN IP is reachable from
   its client subnet; successful VPN authentication alone does not prove routing.
5. Allow the chosen path below from VPN clients to the tunnel listener. Do not
   broadly expose the tunnel port to the Internet.

Our examples place SSH and VPN on the same server. Separate hosts require
additional routing/firewall configuration between them. On Linux,
`ip -4 -brief address` lists interface addresses. `tun0` is only an example;
WireGuard often uses `wg0`. Choose by traffic path, not by VPN product name.

## 3. Choose one of three access paths

### A: Direct access to the server VPN IP — simplest new setup

```text
phone: http://10.8.0.1:18123
  -> VPN -> server 10.8.0.1:18123 -> SSH tunnel -> HA:8123
```

- App: bind address `10.8.0.1`, remote port `18123`.
- SSH server: `GatewayPorts clientspecified`.
- For a restricted tunnel user: `PermitListen 10.8.0.1:18123`.
- Firewall: allow this port from the intended VPN client network.
- The VPN IP must exist on the server when SSH establishes the listener.
- Configure the phone HA URL as `http://10.8.0.1:18123`.

No additional loopback DNAT rules are needed. Your home HA IP is not the remote
URL for this option.

### B: Keep the familiar HA IP on the phone — forward to loopback

```text
phone: http://192.168.50.10:8123
  -> VPN -> server: DNAT 192.168.50.10:8123 to 127.0.0.1:18123
  -> SSH tunnel -> HA:8123
```

- App: bind address **127.0.0.1**, remote port 18123.
- SSH server: `GatewayPorts no`, or `clientspecified` with a loopback request.
- The phone must route that familiar destination through the VPN to the server.
  For example OpenVPN can supply `push "route 192.168.50.10 255.255.255.255"`.
  Check existing routes and overlapping networks first.
- The server translates only the selected VPN request to its local tunnel port.

An illustrative nftables configuration, **not a script to overwrite a firewall**:

```text
table ip nat {
    chain PREROUTING {
        type nat hook prerouting priority dstnat; policy accept;
        iifname "tun0" ip daddr 192.168.50.10 tcp dport 8123 dnat to 127.0.0.1:18123
    }
    chain POSTROUTING {
        type nat hook postrouting priority srcnat; policy accept;
        ip saddr 127.0.0.1 ip daddr 10.8.0.0/24 masquerade
    }
}
```

Read and back up existing rules with `sudo nft list ruleset`, then integrate
suitable rules with your existing firewall management. Do not run `flush ruleset`.
Validate a proposed file before applying it with `sudo nft -c -f FILE`.
On Linux, loopback DNAT also needs suitable `route_localnet` on the VPN interface,
commonly `net.ipv4.conf.tun0.route_localnet=1`. Configure only the intended,
protected interface and persist it with VPN startup; the interface may not exist
at boot yet. Routing, return traffic and filtering must match your system.
NAT translates addresses; it is not an access-control firewall. These IPv4
examples do not automatically protect IPv6.

**Keep loopback for an already working B setup.** Do not switch the app to the
VPN IP while DNAT still targets loopback. An existing DNAT rule still targets
the old remote port until you deliberately change it for a new test port.

### C: Reverse proxy on the same SSH server

```text
browser -> HTTPS reverse proxy on server
        -> 127.0.0.1:18123 -> SSH tunnel -> HA:8123
```

App address 127.0.0.1, SSH setting `GatewayPorts no`. Enable WebSockets in the
proxy. Configure HA trusted_proxies only for actual HTTP proxies: an SSH tunnel
does not add HTTP proxy headers. A proxy in its own container has a separate
loopback/network namespace; configure its path to the host separately.

### Why can the bind address appear to be ignored?

| SSH server setting | Effect |
| --- | --- |
| GatewayPorts no | Loopback only, suitable for B/C |
| GatewayPorts clientspecified | Client chooses address, suitable for A/B/C |
| GatewayPorts yes | Forces wildcard binding, even if app requests loopback |

127.0.0.1 is the app's restricted request, not a guarantee against an overriding
server policy. Inspect the actual listener:

```sh
sudo ss -ltnp | grep ':18123'
```

Expect A: 10.8.0.1:18123; B/C: loopback. 0.0.0.0 or [::] means all respective
IPv4/IPv6 interfaces. Internet reachability then also depends on the firewalls.
For Lightsail check IPv4 and IPv6 rules separately, including broad port ranges.

## 4. Prepare a dedicated SSH account and client key

| Key | Destination | Secret? |
| --- | --- | --- |
| Private client key | App as id_ed25519 | Yes |
| Matching client public key (.pub) | Server authorized_keys | No |
| Public server host key | App known_hosts | No |

These public keys serve different purposes: the client key allows login; the
server host key proves server identity. Generate a dedicated tunnel key on a
trusted computer:

```sh
ssh-keygen -t ed25519 -f ha_tunnel -C home-assistant-tunnel
```

Leave the passphrase empty for unattended startup. This produces ha_tunnel
(private) and ha_tunnel.pub (public). Prefer a separate tunnel account over a
server administration key. Ubuntu example, from an existing admin console:

```sh
sudo adduser --disabled-password --gecos "" ha-tunnel
sudo install -d -m 700 -o ha-tunnel -g ha-tunnel /home/ha-tunnel/.ssh
sudoedit /home/ha-tunnel/.ssh/authorized_keys
```

Paste the **complete line from ha_tunnel.pub** into that file. Then:

```sh
sudo chown ha-tunnel:ha-tunnel /home/ha-tunnel/.ssh/authorized_keys
sudo chmod 600 /home/ha-tunnel/.ssh/authorized_keys
```

Your OS account policy must permit public-key authentication. Retain your admin
access. The following restriction is for **B/C**. Back up SSH configuration,
review existing Include/Match directives and place the block appropriately at
the end of the effective configuration:

```text
Match User ha-tunnel
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding remote
    AllowStreamLocalForwarding no
    GatewayPorts no
    PermitListen 127.0.0.1:18123
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    PermitTunnel no
    MaxSessions 0
```

For A instead use GatewayPorts clientspecified and PermitListen 10.8.0.1:18123.
Update PermitListen when changing ports. MaxSessions 0 prevents shell/SFTP
sessions but allows forwarding. Match applies until the next Match/end of file;
do not blindly append duplicate global settings. Keep an admin console open.
Validate before reloading:

```sh
sudo sshd -t
```

Only if successful: `sudo systemctl reload ssh` on Ubuntu; other systems may
name the service sshd. For user-specific rules, inspect effective values with
`sshd -T -C user=ha-tunnel,host=CLIENTNAME,addr=CLIENT-IP` using real values.
Reconnect the app after changing listener policies.

## 5. Configure the app and find its folder

Add the repository in the HA app store and install the app. Enter your own
values under Configuration and save; B/C example:

```yaml
ssh_host: 203.0.113.10
ssh_port: 22
ssh_user: ha-tunnel
remote_bind_address: 127.0.0.1
remote_port: 18123
target_host: homeassistant
target_port: 8123
use_autossh: true
```

For A set remote_bind_address to the actual server VPN IP. The SSH host is the
reachable SSH endpoint, not necessarily its VPN IP.

| Field / YAML key | What to enter |
| --- | --- |
| SSH host / ssh_host | Reachable server IP or DNS name, not a URL |
| SSH port / ssh_port | SSH service port, default 22 |
| SSH user / ssh_user | Account whose authorized_keys permits your client key |
| Bind address / remote_bind_address | Address on the external server for A/B/C |
| Port on server / remote_port | Free external-server TCP port, default 18123 |
| Destination host / target_host | HA reachable from the app, default homeassistant |
| Destination port / target_port | HA port, default 8123 |
| Use autossh / use_autossh | true: extra process supervision; both modes reconnect |

The target is reachable
from the app: usually homeassistant, alternatively HA's LAN IP. localhost would
mean the app itself. If HA uses TLS, set the corresponding port; this app
transports TCP and does not convert HTTP to HTTPS.

**Supervisor creates the folder on the first start.** After saving, click Start
once. Since version 0.1.2 the app stays running and waits for both nonempty files.
The log shows `Setup: waiting ...`; no SSH connection is made yet. After both
files are uploaded, the app checks the key and starts the tunnel automatically
within about five seconds. Missing or empty files are not an error at this stage.
The Configuration page includes setup help under SSH host, with file names and
the help address. HA does not support a custom information box there; depending
on the frontend version, copy the address as text.

Open through Samba or a file editor with access to app configuration folders:

```text
/app_configs/<repository-id>_reverse_ssh/
    id_ed25519
    known_hosts
```

The folder is **app_configs**, not apps_conf and not HA's general config folder.
For this repository the subfolder is normally 3aff0a81_reverse_ssh; forks/other
repositories have a different ID. The HA app-page URL also includes its ID.
Local installation: local_reverse_ssh. Inside the app this folder is /config.
Refresh your file view after the first start if the folder is missing.

## 6. Fill the two files

### id_ed25519: private login key

Copy the **entire generated ha_tunnel file** into the app folder as id_ed25519.
Do not use ha_tunnel.pub. The structure looks like this:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
<COMPLETE CONTENT OF YOUR OWN PRIVATE KEY FILE>
-----END OPENSSH PRIVATE KEY-----
```

This is intentionally not a usable sample key. Preserve every real line and
boundary of your file. Do not prepend a host/user line. Compatible RSA/PEM keys
can also use this fixed filename, retaining their own boundary lines. Export
PuTTY PPK to OpenSSH format first; renaming alone does not convert it. Version
0.1.x does not support interactive passphrase prompts.

Never post private keys in chat, screenshots or GitHub. The app reads the sources
and makes private runtime copies with permissions 600. HA backups may contain
the keys: protect backups accordingly. No private-key paste field is provided
in the Configuration form.

### known_hosts: server identity

From a trusted server console, such as the Lightsail browser console:

```sh
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
```

Read only the **.pub file**. Output starts with ssh-ed25519 AAAA... and may have
a comment. Put one complete line in known_hosts in this format:

```text
203.0.113.10 ssh-ed25519 <COMPLETE_PUBLIC_SERVER_HOST_KEY>
```

Replace the address with ssh_host and the placeholder with the complete second
field of the server output. Do not retain angle brackets or a truncated key.
The optional comment can be omitted. This is **not** your client public key!
If ssh_host is a DNS name, use that exact name. For SSH port 2222:

```text
[vpn.example.org]:2222 ssh-ed25519 <COMPLETE_PUBLIC_SERVER_HOST_KEY>
```

ssh-keyscan only collects candidate keys. Confirm their identity against a
fingerprint obtained through an independent trusted server console. Do not
disable host verification. Save both files without an extra .txt extension.
Windows CRLF is normalized in runtime copies. Restart after changing files for
an already running tunnel. An invalid or passphrase-protected key stops the app
with an error; correct the file and start again.

## 7. Start and verify

1. Check all eight configuration values and both files, then start the app.
2. Open Log. INFO: Starting tunnel client is not proof of successful connection.
3. On the external server test with **GET**, for B/C:

   ```sh
   curl --max-time 10 -o /dev/null -s -w 'HTTP %{http_code}\n' http://127.0.0.1:18123/
   ```

   For A replace the address with 10.8.0.1. For HA TLS use https:// with proper
   certificate validation. HTTP 200 confirms a response through the tunnel.
   curl -I sends HEAD; HA may return 405 Method Not Allowed, so use GET here.
4. Inspect `sudo ss -ltnp | grep ':18123'` and compare with option A/B/C.
5. On the phone disable Wi-Fi, enable mobile data and VPN, open the right URL,
   log in and test live updates/WebSockets and the HA functions you actually use.
6. Stop the app: the new path should fail. Start it: access should return.
   This distinguishes the new tunnel from an existing one.
7. Enable Start on boot afterward. Test planned restarts and reconnection with
   an independent administrative path available.

## 8. Replace an existing tunnel

Initially use a different server port: old tunnel 8123, new app 18123, both
leading to HA port 8123. With B, existing DNAT still points to the old port.
Explicitly test the new port on the server or deliberately change the forwarding.

To retain the phone configuration: keep local HA access available, stop the app,
set its server port to the old port, adjust PermitListen, **stop** the old
container, start the app. Two tunnels cannot occupy the same listener. With B,
DNAT must target the chosen loopback port. Rollback: stop app, start old container.

After successful verification disable the old autostart: a stopped container
with a restart policy can return after a host reboot. Later remove that specific
standalone container to eliminate this cause of the unsupported-software warning.
Do not delete unrelated Docker containers.

## 9. Troubleshooting and reconnection

| Symptom | Check |
| --- | --- |
| No folder / empty log | Start clicked? File view refreshed? Correct app_configs folder? |
| Missing files | Exact filenames, correct app ID, no .txt suffix |
| Invalid key / passphrase | Complete private OpenSSH/PEM key, not public key or PPK |
| No ED25519 host key is known | Server host key for exact SSH host and port in known_hosts |
| Host key verification failed | Verify server identity; never blindly accept a changed key |
| Permission denied (publickey) | User, matching client public key in authorized_keys, permissions/account policy |
| Remote port forwarding failed | Port occupied? PermitListen, GatewayPorts, VPN IP exists? |
| Only Starting message, no phone access | GET test, actual listener, VPN routes, NAT and firewall |
| Loopback selected, wildcard listener | GatewayPorts yes or user-specific Match policy |

Both modes reconnect. The launcher waits ten seconds after its client exits.
Autossh supervises SSH using its own retry/backoff; the ten-second delay applies
only when autossh itself exits. Keepalives: 30 seconds, three missed replies.
No extra monitor port is opened. A failed HA HTTP service is not automatically
detected by these process/SSH checks.

## References

- [HA app configuration files](https://contributors.home-assistant.io/apps/guides/options/)
- [OpenSSH server options](https://man.openbsd.org/sshd_config)
- [OpenVPN routing](https://openvpn.net/community-docs/setting-up-routing/)
- [nftables NAT](https://wiki.nftables.org/wiki-nftables/index.php/Performing_Network_Address_Translation_(NAT))
- [Linux route_localnet](https://docs.kernel.org/networking/ip-sysctl.html)
- [Lightsail IPv4/IPv6 firewalls](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html)
