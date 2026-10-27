# Einrichtung (Deutsch)

Experimentelle App für Home Assistant OS. Voraussetzung ist ein eigener
SSH-Server, zum Beispiel auf Lightsail. Ein VPN ist optional. Die App baut
einen TCP-Tunnel auf; sie installiert weder VPN noch Reverse Proxy oder TLS.

## Schlüssel und Server

Verwende einen eigenen SSH-Benutzer und einen ausschließlich für diesen Tunnel
erzeugten Ed25519-Schlüssel. Ein administrativer Lightsail-Schlüssel sollte
hierfür nicht wiederverwendet werden. Passwortanmeldung und Schlüssel mit
interaktiver Passphrase werden in Version 0.1.0 nicht unterstützt.

```sh
ssh-keygen -t ed25519 -f ha_tunnel -C home-assistant-tunnel
```

Für unbeaufsichtigten Start bleibt die Passphrase leer. Der öffentliche Teil
`ha_tunnel.pub` gehört auf den SSH-Server in authorized_keys; der private Teil
bleibt geheim. Beschränke den Serverbenutzer auf Remote-Portweiterleitung.
Ein vollständiges Beispiel mit `Match User`, `PermitListen` und `MaxSessions 0`
steht in der [englischen Anleitung](DOCS.md). Vor dem Neuladen `sshd -t` prüfen
und eine bestehende Administrationsverbindung offen lassen.

## Dateien hochladen

Nach der Installation öffnest du über Samba oder einen geeigneten Dateieditor
den App-Konfigurationsordner:
`/app_configs/<Repository-ID>_reverse_ssh/`.
Bei lokaler Installation heißt er `local_reverse_ssh`. Die Repository-ID wird
von HA vergeben. Dieser Ordner erscheint innerhalb der App als `/config`.

Lege dort zwei Dateien ab:

- **id_ed25519:** der private Schlüssel, entsprechend umbenannt.
- **known_hosts:** der überprüfte Hostkey des SSH-Servers.

Den Fingerabdruck des Hostkeys über einen vertrauenswürdigen Zugang, etwa die
Serverkonsole, abgleichen. `ssh-keyscan` allein beweist nicht die Identität.
Bei abweichendem SSH-Port muss der Eintrag `[host]:port` verwenden. Host/IP
muss zum Feld `ssh_host` passen. Die Hostkey-Prüfung bleibt immer aktiv.
Nach Austausch der Dateien die App neu starten. Windows-Zeilenenden werden
in privaten Laufzeitkopien normalisiert; die hochgeladenen Dateien bleiben
unverändert. Schlüssel können in HA-Backups enthalten sein: Backups schützen.
Die erste Version hat bewusst kein Schlüsselfeld zum Einfügen in Optionen.

## Einstellungen

| Feld | Vorgabe | Bedeutung |
| --- | --- | --- |
| SSH-Host | leer, erforderlich | Erreichbare IP oder DNS-Name des SSH-Servers |
| SSH-Port | 22 | Port des SSH-Dienstes |
| SSH-Benutzer | ha-tunnel | Eigener Tunnelbenutzer auf dem Server |
| Bind-Adresse auf dem Server | 127.0.0.1 | IP, an der der entfernte Tunnel lauscht |
| Port auf dem Server | 18123 | Freier entfernter TCP-Port |
| Zielhost | homeassistant | Aus der App erreichbarer HA-Host |
| Zielport | 8123 | HA-Port, auch bei eigenem TLS anpassen |
| autossh verwenden | an | SSH-Prozess zusätzlich mit autossh überwachen |

Der SSH-Host kann die öffentliche Lightsail-IP sein; die Bind-Adresse kann
gleichzeitig die VPN-IP dieses Servers sein. Das sind zwei unterschiedliche
Einstellungen. `localhost` als Ziel wäre die App selbst, nicht HA Core.

Standardmäßig ist der entfernte Port nur auf dem SSH-Server erreichbar. Das
passt zu einem dort laufenden Reverse Proxy. Für direkten Zugriff über das
VPN: dessen Server-IP als Bind-Adresse setzen und auf dem SSH-Server
`GatewayPorts clientspecified` sowie passendes `PermitListen` konfigurieren.
Die Firewall auf die gewünschten VPN-Clients beschränken. `0.0.0.0` kann den
Zugriff öffentlich machen und ist deshalb keine Vorgabe.

Der Starter verbindet nach Ende seines Clientprozesses mit zehn Sekunden Pause
neu. autossh verbindet seinen SSH-Unterprozess intern nach eigener Warte- und
Backoff-Logik neu; die zehn Sekunden gelten dort erst, wenn autossh selbst endet.
Keepalives prüfen alle 30 Sekunden mit maximal drei fehlenden Antworten.
autossh nutzt keinen zusätzlichen Monitor-Port. Ein laufender SSH-Prozess
beweist noch nicht, dass HA über den gesamten Zugriffsweg erreichbar ist.

## Sicher umstellen

Zunächst einen anderen freien entfernten Port verwenden, inklusive Freigabe
in `PermitListen`. Bestehenden Tunnel unverändert weiterlaufen lassen. Vom
Server aus mit `curl -I http://127.0.0.1:18123/` testen; Adresse, Port und TLS
bei Bedarf anpassen. Danach Anmeldung, WebSockets, App-Neustart und Erholung
nach Netzunterbrechung testen, jeweils mit und ohne autossh.

Erst danach den alten Container stilllegen. Rückweg: App stoppen und bisherigen
Tunnel starten. Die App verändert keine bestehenden HA- oder Servereinstellungen.
HA-Anmeldung und passendes TLS bleiben erforderlich. Vertrauenswürdige Proxys
in HA nur passend zur tatsächlichen HTTP-Proxy-Topologie konfigurieren.

Bei Fehlern das App-Protokoll prüfen: Hostkey, Benutzer/Schlüssel, Portbelegung,
`PermitListen`, `GatewayPorts` und HA-Ziel sind die typischen Ursachen.
Weitere Details stehen in der [englischen Anleitung](DOCS.md).
