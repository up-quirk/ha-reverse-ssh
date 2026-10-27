"""Disposable SSH + HTTP fixture. Credentials live only in the test volume."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess

ROOT = Path('/fixture')
CONFIG = ROOT / 'config'
DATA = ROOT / 'data'
CONFIG.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)


def key(path):
    if not path.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(path)], check=True)


key(ROOT / 'server_key')
key(CONFIG / 'id_ed25519')
(CONFIG / 'known_hosts').write_text('ssh-server ' + (ROOT / 'server_key.pub').read_text())
(CONFIG / 'known_hosts.good').write_bytes((CONFIG / 'known_hosts').read_bytes())
(DATA / 'options.json').write_text(json.dumps(dict(
    ssh_host='ssh-server', ssh_port=22, ssh_user='tunnel',
    remote_bind_address='127.0.0.1', remote_port=18123,
    target_host='ssh-server', target_port=8123, use_autossh=True)))
account = pwd.getpwnam('tunnel')
authorized = Path('/home/tunnel/.ssh')
authorized.mkdir(mode=0o700, exist_ok=True)
(authorized / 'authorized_keys').write_bytes((CONFIG / 'id_ed25519.pub').read_bytes())
os.chown(authorized, account.pw_uid, account.pw_gid)
os.chown(authorized / 'authorized_keys', account.pw_uid, account.pw_gid)
os.chmod(authorized / 'authorized_keys', 0o600)
Path('/run/sshd').mkdir(exist_ok=True)
Path('/test-sshd.conf').write_text('''
Port 22
ListenAddress 0.0.0.0
HostKey /fixture/server_key
PidFile /run/test-sshd.pid
PasswordAuthentication no
KbdInteractiveAuthentication no
AuthenticationMethods publickey
AllowUsers tunnel
AllowTcpForwarding remote
PermitListen 127.0.0.1:18123
GatewayPorts no
AllowAgentForwarding no
X11Forwarding no
PermitTTY no
MaxSessions 0
''')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'reverse-ssh-fixture-ok'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


sshd = subprocess.Popen(['/usr/sbin/sshd', '-D', '-e', '-f', '/test-sshd.conf'])
signal.signal(signal.SIGTERM, lambda *_: exit(0))
try:
    HTTPServer(('0.0.0.0', 8123), Handler).serve_forever()
finally:
    sshd.terminate()
    sshd.wait(timeout=5)
