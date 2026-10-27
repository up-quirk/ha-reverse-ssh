# Reverse SSH Tunnel: Schritt für Schritt

Diese App (früher Add-on) verbindet HA mit deinem eigenen externen SSH-Server.
Ein Port auf diesem Server führt durch den Tunnel zurück zu HA. Ein VPN kann
den Zugriff auf deine Geräte begrenzen. Die App installiert weder das VPN
noch einen Reverse Proxy und ändert keine Serverkonfiguration.

## 1. Welche Komponenten brauche ich?

```text
ZU HAUSE                       EXTERNER SERVER                 UNTERWEGS
HA OS                          VPS / z.B. Lightsail            iPhone / PC
+-------------------+          +----------------------+       +------------+
| Reverse-SSH-App   |-- SSH --->| SSH-Dienst :22        |       | VPN-Client |
| verbindet nach  |          |                      |<==VPN==|            |
| aussen           |          | VPN-Dienst            |       +------------+
|                   |          | z.B. OpenVPN          |
| HA Core :8123    |<--Tunnel--| Tunnel-Port :18123   |<-- Anfrage aus VPN
+-------------------+          +----------------------+
```

SSH und VPN sind **zwei verschiedene Verbindungen**: Die App verbindet sich
vom Heimnetz zum SSH-Dienst. Das Telefon verbindet sich zum VPN-Dienst. Der
externe Server verbindet diese Zugriffswege. Am Heimrouter ist normalerweise
keine eingehende Portfreigabe nötig. HA verlangt weiterhin eine Anmeldung.

Alle folgenden Werte sind **austauschbare Beispiele**, keine fertigen Zugangsdaten:

| Bedeutung | Beispiel |
| --- | --- |
| Öffentliche SSH-Adresse | `203.0.113.10` (Dokumentationsadresse, ersetzen!) |
| SSH-Port / eigener Tunnelbenutzer | `22` / `ha-tunnel` |
| VPN-Interface / Server-VPN-IP | `tun0` / `10.8.0.1` |
| VPN-Clientnetz | `10.8.0.0/24` |
| Tunnel-Port auf dem Server | `18123` |
| HA-Ziel aus der App | `homeassistant:8123` |
| Gewohnte HA-Adresse für Variante B | `192.168.50.10:8123` |

Server-Port `18123` und HA-Port `8123` müssen nicht gleich sein. Die App öffnet
keinen neuen eingehenden Port am HA-Host. `127.0.0.1` bezeichnet immer den
jeweiligen Rechner bzw. Container selbst, nicht automatisch Home Assistant.

## 2. Was muss das externe VPN können?

Voraussetzung ist ein funktionierendes, authentifiziertes VPN zum externen
Server, beispielsweise OpenVPN oder WireGuard. Die vollständige Einrichtung
mit eigenen Zertifikaten/Schlüsseln und Clientprofilen erfolgt nach der
Anleitung deines VPN-Produkts. Diese App ersetzt diesen Schritt nicht.

1. VPN-Server einrichten und eigenes Clientprofil auf dem Telefon importieren.
2. Den verwendeten VPN-Port in Cloud- und Server-Firewall zulassen, etwa UDP
   `1194` bei vielen OpenVPN-Installationen. Dein tatsächlicher Port kann abweichen.
3. SSH auf dem externen Server für den HA-Standort erreichbar machen, meist TCP `22`.
4. VPN am Telefon verbinden. Die VPN-IP des Servers muss aus dem Clientnetz
   erreichbar sein; erfolgreiche VPN-Anmeldung allein beweist die Route nicht.
5. Den unten gewählten Weg vom VPN zum Tunnel-Port zulassen. Den Tunnel-Port
   nicht pauschal öffentlich im Internet freigeben.

VPN und SSH laufen hier auf demselben Server. Bei getrennten Rechnern brauchst
du zusätzliche Routen und Firewall-Regeln zwischen ihnen. Auf Linux zeigt
`ip -4 -brief address` die Adressen. `tun0` ist nur ein Beispiel; WireGuard
verwendet oft `wg0`. Entscheidend ist der Zugriffsweg, nicht der VPN-Produktname.

## 3. Eine von drei Varianten wählen

### A: Direkt auf die VPN-IP zugreifen – einfacher Neueinstieg

```text
iPhone: http://10.8.0.1:18123
  -> VPN -> Server 10.8.0.1:18123 -> SSH-Tunnel -> HA:8123
```

- App: Bind-Adresse `10.8.0.1`, Server-Port `18123`.
- SSH-Server: `GatewayPorts clientspecified`.
- Für einen eingeschränkten Tunnelbenutzer: `PermitListen 10.8.0.1:18123`.
- Firewall: diesen Port aus dem vorgesehenen VPN-Netz erlauben.
- Die VPN-IP muss beim Aufbau des SSH-Tunnels bereits auf dem Server existieren.
- Im Telefon `http://10.8.0.1:18123` als HA-Ziel eintragen.

Keine zusätzliche DNAT-Regel auf Loopback nötig. Die lokale HA-Adresse ist
von unterwegs nicht die richtige URL für Variante A.

### B: Gewohnte HA-IP bleibt im Telefon – Weiterleitung auf Loopback

```text
iPhone: http://192.168.50.10:8123
  -> VPN -> Server: DNAT 192.168.50.10:8123 auf 127.0.0.1:18123
  -> SSH-Tunnel -> HA:8123
```

- App: Bind-Adresse **`127.0.0.1`**, Server-Port `18123`.
- SSH-Server: `GatewayPorts no`, oder `clientspecified` mit Loopback als App-Adresse.
- Das Telefon routet die gewohnte HA-IP über das VPN zum Server. Beispielsweise
  kann OpenVPN die Hostroute `push "route 192.168.50.10 255.255.255.255"`
  bereitstellen. Bestehende Routen und überlappende Netze zuerst prüfen.
- Auf dem Server übersetzt eine gezielte Regel diese Anfrage auf den Tunnel-Port.

Beispiel zur Erklärung von nftables, **kein Skript zum Überschreiben einer Firewall**:

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

Vorhandene Regeln mit `sudo nft list ruleset` lesen und sichern; passende Regeln
in die bestehende Verwaltung integrieren. Kein `flush ruleset` ausführen.
Eine Datei kann vor dem Anwenden mit `sudo nft -c -f DATEI` geprüft werden.
DNAT zu Loopback erfordert auf Linux außerdem passendes `route_localnet` am
VPN-Interface, typischerweise `net.ipv4.conf.tun0.route_localnet=1`. Nur für das
betroffene geschützte Interface einrichten und mit dem VPN-Start persistent
setzen; das Interface fehlt beim Systemstart möglicherweise noch. Routing,
Rückweg und Filter müssen zum System passen. NAT ist keine Firewall-Sperre.
Diese IPv4-Beispiele schützen nicht automatisch IPv6.

**Bei einem funktionierenden Aufbau B bleibt Loopback richtig.** Nicht auf die
VPN-IP wechseln, während DNAT weiter auf Loopback zeigt. Eine alte DNAT-Regel
zeigt auch bei einem neuen Testport weiter auf den alten Port, bis du sie änderst.

### C: Reverse Proxy auf demselben SSH-Server

```text
Browser -> HTTPS-Proxy auf dem Server
        -> 127.0.0.1:18123 -> SSH-Tunnel -> HA:8123
```

App-Adresse `127.0.0.1`, SSH-Einstellung `GatewayPorts no`. Der Proxy muss
WebSockets unterstützen. HA `trusted_proxies` nur für tatsächliche HTTP-Proxys
konfigurieren: SSH allein fügt keine Proxy-Header hinzu. Wenn der Proxy in
einem eigenen Container läuft, ist dessen Loopback ein anderer Netzwerk-
Namensraum; die Verbindung zum Host muss gesondert eingerichtet werden.

### Warum kann die Bind-Adresse scheinbar ignoriert werden?

| SSH-Server-Einstellung | Wirkung |
| --- | --- |
| `GatewayPorts no` | Nur Loopback, passend für B/C |
| `GatewayPorts clientspecified` | Client darf die Adresse wählen, passend für A/B/C |
| `GatewayPorts yes` | Erzwingt Wildcard-Bindung, auch wenn die App Loopback anfordert |

`127.0.0.1` ist eine eingeschränkte Anforderung der App, keine Garantie gegen
eine überschreibende Serverkonfiguration. Den tatsächlichen Listener prüfen:

```sh
sudo ss -ltnp | grep ':18123'
```

Erwartet: A `10.8.0.1:18123`; B/C Loopback. `0.0.0.0` bzw. `[::]` bedeutet alle
IPv4- bzw. IPv6-Schnittstellen. Dann hängt Internetzugriff zusätzlich von den
Firewalls ab. Bei Lightsail IPv4 und IPv6 separat prüfen, auch breite Portbereiche.

## 4. Eigenen SSH-Benutzer und Schlüssel vorbereiten

| Schlüssel | Wo gehört er hin? | Geheim? |
| --- | --- | --- |
| Privater Client-Key | App als `id_ed25519` | Ja |
| Zugehöriger Client-Public-Key (`.pub`) | Server: `authorized_keys` | Nein |
| Öffentlicher Server-Hostkey | App: `known_hosts` | Nein |

Die öffentlichen Schlüssel haben verschiedene Aufgaben: Der Client-Key erlaubt
die Anmeldung, der Server-Hostkey bestätigt die Identität des Servers.

Auf einem vertrauenswürdigen Rechner einen eigenen Tunnel-Key erzeugen:

```sh
ssh-keygen -t ed25519 -f ha_tunnel -C home-assistant-tunnel
```

Für unbeaufsichtigten Start die Passphrase leer lassen. Es entstehen `ha_tunnel`
(privat) und `ha_tunnel.pub` (öffentlich). Einen administrativen Schlüssel
möglichst nicht wiederverwenden. Auf Ubuntu über die vorhandene Admin-Konsole:

```sh
sudo adduser --disabled-password --gecos "" ha-tunnel
sudo install -d -m 700 -o ha-tunnel -g ha-tunnel /home/ha-tunnel/.ssh
sudoedit /home/ha-tunnel/.ssh/authorized_keys
```

Die **vollständige Zeile aus `ha_tunnel.pub`** in diese Datei einsetzen. Danach:

```sh
sudo chown ha-tunnel:ha-tunnel /home/ha-tunnel/.ssh/authorized_keys
sudo chmod 600 /home/ha-tunnel/.ssh/authorized_keys
```

Die Kontorichtlinien müssen Public-Key-Anmeldung erlauben. Admin-Zugang behalten.
Für **B/C** eignet sich der folgende Match-Block. Zuerst die SSH-Konfiguration
sichern und vorhandene Includes/Match-Blöcke prüfen. Passend am Ende einordnen:

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

Für A stattdessen `GatewayPorts clientspecified` und
`PermitListen 10.8.0.1:18123`. Bei Portwechsel PermitListen ebenfalls ändern.
`MaxSessions 0` verhindert Shell/SFTP, erlaubt aber die Weiterleitung. Match
wirkt bis zum nächsten Match bzw. Dateiende. Keine globalen Optionen blind
doppelt anhängen. Eine administrative Konsole offen lassen. Vor Neuladen:

```sh
sudo sshd -t
```

Nur wenn fehlerfrei: unter Ubuntu `sudo systemctl reload ssh`; auf anderen
Systemen kann der Dienst `sshd` heißen. Benutzerspezifische Werte gegebenenfalls
mit `sshd -T -C user=ha-tunnel,host=CLIENTNAME,addr=CLIENT-IP` und echten Werten
prüfen. Die App muss nach Änderungen am Listener neu verbinden.

## 5. App konfigurieren und Ordner finden

Repository im HA-App-Store hinzufügen, App installieren. Konfiguration mit
eigenen Werten befüllen und speichern; Beispiel B/C:

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

Für A nur `remote_bind_address` auf die tatsächliche Server-VPN-IP setzen.

| Feld im Formular / YAML | Was eintragen? |
| --- | --- |
| SSH-Host / `ssh_host` | Erreichbare IP oder DNS-Name des SSH-Servers, keine URL |
| SSH-Port / `ssh_port` | Port des SSH-Dienstes, Vorgabe 22 |
| SSH-Benutzer / `ssh_user` | Konto, dessen authorized_keys deinen Client-Key erlaubt |
| Bind-Adresse / `remote_bind_address` | Adresse auf dem externen Server nach Variante A/B/C |
| Port auf dem Server / `remote_port` | Freier TCP-Port auf dem externen Server, Vorgabe 18123 |
| Zielhost / `target_host` | Aus der App erreichbares HA, Vorgabe homeassistant |
| Zielport / `target_port` | HA-Port, Vorgabe 8123 |
| autossh / `use_autossh` | true: zusätzliche Prozessüberwachung; beide Modi verbinden neu |

SSH-Host ist die erreichbare SSH-Adresse, nicht zwangsläufig die VPN-IP.
Zielhost ist aus der App erreichbar, normalerweise `homeassistant`, alternativ
die HA-LAN-IP. `localhost` wäre die App selbst. Bei eigenem HA-TLS den passenden
Port verwenden; die App transportiert TCP, sie wandelt HTTP nicht in HTTPS um.

**Der Supervisor legt den Ordner beim ersten Startversuch an.** Nach dem
Speichern einmal Starten klicken. Ohne Schlüsseldateien beendet sich die App
erwartungsgemäß, bevor sie eine SSH-Verbindung aufbaut. Einen aktivierten
Watchdog bis zum Abschluss der Einrichtung gegebenenfalls ausschalten.

Über Samba oder einen geeigneten Dateieditor öffnen:

```text
/app_configs/<Repository-ID>_reverse_ssh/
    id_ed25519
    known_hosts
```

Es heißt **`app_configs`**, nicht `apps_conf` und nicht der allgemeine HA-Ordner
`config`. Bei diesem Repository heißt der Unterordner üblicherweise
`3aff0a81_reverse_ssh`; Forks/andere Repositories haben andere IDs. Die ID steht
auch in der URL der HA-App-Seite. Lokale Installation: `local_reverse_ssh`.
Innerhalb der App heißt der Ordner `/config`. Nach dem Startversuch Ansicht
aktualisieren, wenn der Ordner noch nicht angezeigt wird.

## 6. Die beiden Dateien befüllen

### `id_ed25519`: privater Anmeldeschlüssel

Die erzeugte Datei **`ha_tunnel` vollständig kopieren**, im App-Ordner als
`id_ed25519` speichern. Nicht die `.pub`-Datei verwenden. Der Aufbau ist etwa:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
<VOLLSTAENDIGER INHALT DEINER PRIVATEN SCHLUESSELDATEI>
-----END OPENSSH PRIVATE KEY-----
```

Das ist absichtlich kein verwendbarer Beispielschlüssel. Alle echten Zeilen
und Begrenzungen deiner Datei unverändert übernehmen. Keine IP/Benutzerzeile
davor schreiben. Auch kompatible RSA-/PEM-Keys können unter dem festen Namen
verwendet werden, mit ihren eigenen Begrenzungszeilen. PuTTY-PPK zuerst nach
OpenSSH exportieren: Umbenennen allein konvertiert nicht. Version 0.1.x
unterstützt keine interaktive Passphrase.

Private Keys nie in Chats, Screenshots oder GitHub veröffentlichen. Die App
liest die Quellen nur und erstellt private Laufzeitkopien mit Rechten `600`.
HA-Backups können Schlüssel enthalten: Backups schützen. Es gibt bewusst kein
Schlüsselfeld zum Einfügen in die Konfigurationsmaske.

### `known_hosts`: Identität des Servers

Über eine vertrauenswürdige Serverkonsole, etwa die Lightsail-Browserkonsole:

```sh
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
```

Nur die **`.pub`-Datei** auslesen. Die Ausgabe beginnt mit
`ssh-ed25519 AAAA...` und kann einen Kommentar haben. In `known_hosts` kommt
eine vollständige Zeile in dieser Form:

```text
203.0.113.10 ssh-ed25519 <VOLLSTAENDIGER_OEFFENTLICHER_SERVER_HOSTKEY>
```

IP durch deinen `ssh_host`, Platzhalter durch das vollständige zweite Feld der
Serverausgabe ersetzen. Keine spitzen Klammern oder gekürzten Schlüssel
übernehmen. Kommentar darf entfallen. Das ist **nicht** dein Client-Public-Key!
Bei DNS-Namen muss genau der konfigurierte Name stehen. Für SSH-Port `2222`:

```text
[vpn.example.org]:2222 ssh-ed25519 <VOLLSTAENDIGER_OEFFENTLICHER_SERVER_HOSTKEY>
```

`ssh-keyscan` sammelt nur Kandidaten. Die Identität anhand des Fingerabdrucks
aus einer unabhängigen vertrauenswürdigen Konsole bestätigen. Hostkey-Prüfung
nicht abschalten. Dateien ohne zusätzliche `.txt`-Endung speichern. CRLF wird
in Laufzeitkopien normalisiert. Nach jeder Dateiänderung die App neu starten.

## 7. Starten und testen

1. Alle acht Konfigurationswerte und beide Dateien prüfen, dann starten.
2. Protokoll öffnen. `INFO: Starting tunnel client` ist noch kein Verbindungsnachweis.
3. Auf dem externen Server mit **GET** testen, für B/C:

   ```sh
   curl --max-time 10 -o /dev/null -s -w 'HTTP %{http_code}\n' http://127.0.0.1:18123/
   ```

   Für A die Adresse auf `10.8.0.1` ändern. Bei HA-TLS `https://` und passende
   Zertifikatsprüfung verwenden. `HTTP 200` bestätigt eine Antwort durch den
   Tunnel. `curl -I` sendet HEAD; HA kann darauf `405 Method Not Allowed` liefern.
4. Listener prüfen: `sudo ss -ltnp | grep ':18123'`, mit A/B/C vergleichen.
5. Am Telefon WLAN aus, Mobilfunk und VPN an. Richtige Zieladresse öffnen,
   anmelden und Live-Aktualisierungen/WebSockets sowie deine HA-Funktionen testen.
6. App stoppen: neuer Zugriffsweg muss ausfallen. App starten: er muss wieder
   funktionieren. So lässt sich der neue von einem alten Tunnel unterscheiden.
7. Danach Start beim Booten aktivieren. Geplante Neustarts und Wiederverbindung
   mit einem zusätzlichen Verwaltungszugang testen.

## 8. Bestehenden Tunnel ersetzen

Parallel zunächst einen anderen Server-Port verwenden: alter Tunnel `8123`,
neue App `18123`, beide mit HA-Zielport `8123`. Bei B zeigt die alte DNAT-Regel
weiter auf den alten Port. Zum Testen den neuen Port explizit am Server
ansprechen oder die Weiterleitung bewusst auf ihn umstellen.

Soll die Telefonadresse unverändert bleiben: lokalen HA-Zugang bereithalten,
neue App stoppen, ihren Server-Port auf den bisherigen setzen, PermitListen
anpassen, alten Container **nur stoppen**, neue App starten. Zwei Tunnel können
denselben Listener nicht gleichzeitig belegen. Bei B muss DNAT auf den gewählten
Loopback-Port zeigen. Rückweg: App stoppen und alten Container wieder starten.

Erst nach erfolgreichem Test alten Autostart deaktivieren: ein nur gestoppter
Container mit Restart-Policy kann nach einem Host-Neustart wiederkommen.
Später den alten Standalone-Container gezielt entfernen, um diese Ursache der
Unsupported-Software-Warnung zu beseitigen. Nicht pauschal andere Container löschen.

## 9. Häufige Fehler und Wiederverbindung

| Symptom | Prüfen |
| --- | --- |
| Kein Ordner / leeres Protokoll | Starten geklickt? Ansicht aktualisiert? Richtiger app_configs-Ordner? |
| Fehlende Dateien | Exakte Namen, richtige App-ID, keine `.txt`-Endung |
| Ungültiger Key / Passphrase | Vollständiger privater OpenSSH-/PEM-Key, kein Public Key oder PPK |
| `No ED25519 host key is known` | Server-Hostkey für richtige SSH-Adresse und Port in known_hosts |
| `Host key verification failed` | Serveridentität prüfen; neuen Key nicht blind akzeptieren |
| `Permission denied (publickey)` | Benutzer, Client-Public-Key in authorized_keys, Rechte/Kontorichtlinien |
| `remote port forwarding failed` | Port belegt? PermitListen, GatewayPorts, VPN-IP vorhanden? |
| Nur Starting-Meldung, kein Telefonzugriff | GET-Test, Listener, VPN-Routen, NAT und Firewall |
| Loopback gewählt, trotzdem Wildcard | GatewayPorts yes oder benutzerspezifischer Match-Block |

Beide Modi verbinden neu. Nach Ende seines Clientprozesses wartet der Starter
zehn Sekunden. autossh überwacht SSH mit eigener Backoff-Logik; die zehn Sekunden
gelten dort erst nach Ende von autossh selbst. Keepalives: 30 Sekunden, drei
fehlende Antworten. Kein zusätzlicher Monitor-Port. Ein defekter HA-HTTP-Dienst
wird dadurch nicht automatisch erkannt.

## Quellen

- [HA: App-Konfigurationsdateien](https://contributors.home-assistant.io/apps/guides/options/)
- [OpenSSH: Serveroptionen](https://man.openbsd.org/sshd_config)
- [OpenVPN: Routing](https://openvpn.net/community-docs/setting-up-routing/)
- [nftables: NAT](https://wiki.nftables.org/wiki-nftables/index.php/Performing_Network_Address_Translation_(NAT))
- [Linux: route_localnet](https://docs.kernel.org/networking/ip-sysctl.html)
- [Lightsail: IPv4-/IPv6-Firewalls](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html)
