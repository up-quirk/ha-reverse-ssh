"""Real local Docker tunnel test. No published ports or real credentials.

Run after building ha-reverse-ssh:dev and ha-reverse-ssh-fixture:dev.
Only resources carrying this invocation's random prefix are removed.
"""
import subprocess
import time
import uuid

PREFIX = 'ha-rssh-test-' + uuid.uuid4().hex[:10]
NETWORK = PREFIX + '-net'
VOLUME = PREFIX + '-files'
SERVER = PREFIX + '-server'
CLIENT = PREFIX + '-client'
PROBE = ("import urllib.request; "
         "print(urllib.request.urlopen('http://127.0.0.1:18123', timeout=2).read().decode())")


def docker(*args, check=True, timeout=45):
    result = subprocess.run(['docker', *args], text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'Docker {args[0]} failed: {result.stderr.strip()}')
    return result


def server_python(code):
    return docker('exec', SERVER, 'python3', '-c', code)


def wait_for(predicate, label, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            print(f'PASS: {label}', flush=True)
            return
        time.sleep(1)
    raise AssertionError(f'Timed out: {label}')


def probe():
    result = docker('exec', SERVER, 'python3', '-c', PROBE, check=False)
    return result.returncode == 0 and result.stdout.strip() == 'reverse-ssh-fixture-ok'


def start_client():
    docker('run', '-d', '--init', '--name', CLIENT, '--network', NETWORK,
           '--mount', f'type=volume,src={VOLUME},dst=/config,volume-subpath=config,readonly',
           '--mount', f'type=volume,src={VOLUME},dst=/data,volume-subpath=data,readonly',
           'ha-reverse-ssh:dev')


def remove_client():
    docker('rm', '-f', CLIENT, check=False)


def main():
    docker('network', 'create', '--internal', NETWORK)
    try:
        docker('volume', 'create', VOLUME)
        docker('run', '-d', '--init', '--name', SERVER, '--network', NETWORK,
               '--network-alias', 'ssh-server', '-v', f'{VOLUME}:/fixture',
               'ha-reverse-ssh-fixture:dev')
        wait_for(lambda: docker('exec', SERVER, 'test', '-f', '/fixture/data/options.json',
                                check=False).returncode == 0, 'fixture initialization')
        # Initial setup stays alive with no credentials, stops cleanly, and
        # picks up later uploads without restarting the client.
        server_python("from pathlib import Path; p=Path('/fixture/config'); "
                      "[(p/n).rename(p/(n+'.saved')) for n in ('id_ed25519','known_hosts')]")
        start_client()
        wait_for(lambda: 'Setup: waiting' in docker('logs', CLIENT).stderr,
                 'initial setup waits for credentials')
        assert docker('inspect', '--format', '{{.State.Running}}', CLIENT).stdout.strip() == 'true'
        assert not probe(), 'Unexpected tunnel before credential upload'
        docker('stop', '--time', '20', CLIENT)
        assert docker('inspect', '--format', '{{.State.ExitCode}}', CLIENT).stdout.strip() == '0'
        print('PASS: clean stop during setup wait', flush=True)
        remove_client()
        start_client()
        wait_for(lambda: 'Setup: waiting' in docker('logs', CLIENT).stderr,
                 'setup waits after restart')
        server_python("from pathlib import Path; p=Path('/fixture/config'); "
                      "[(p/(n+'.saved')).rename(p/n) for n in ('id_ed25519','known_hosts')]")
        wait_for(probe, 'credential upload starts real tunnel without client restart')
        docker('stop', '--time', '20', CLIENT)
        remove_client()
        for autossh in (False, True):
            mode = 'autossh' if autossh else 'ssh'
            server_python("import json; from pathlib import Path; "
                          "p=Path('/fixture/data/options.json'); o=json.loads(p.read_text()); "
                          f"o['use_autossh']={autossh!r}; p.write_text(json.dumps(o))")
            start_client()
            wait_for(probe, f'{mode}: HTTP response through real reverse tunnel')
            permissions = docker('exec', CLIENT, 'stat', '-c', '%a',
                                 '/run/reverse-ssh/id_ed25519').stdout.strip()
            assert permissions == '600', permissions
            print(f'PASS: {mode}: runtime private-key permissions 600', flush=True)
            docker('restart', SERVER)
            wait_for(probe, f'{mode}: reconnect after SSH-server restart', timeout=120)
            docker('stop', '--time', '20', CLIENT)
            status = docker('inspect', '--format', '{{.State.ExitCode}}', CLIENT).stdout.strip()
            assert status == '0', f'Client stop exit code {status}'
            print(f'PASS: {mode}: graceful stop (exit 0)', flush=True)
            remove_client()

        # Reserve the reverse listener; forwarding must fail, then recover
        # once a fixture restart releases the occupied port.
        docker('exec', '-d', SERVER, 'python3', '-c',
               "import socket,time; from pathlib import Path; "
               "s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); "
               "s.bind(('127.0.0.1',18123)); s.listen(); "
               "Path('/tmp/port-ready').touch(); time.sleep(120)")
        wait_for(lambda: docker('exec', SERVER, 'test', '-f', '/tmp/port-ready',
                                check=False).returncode == 0, 'occupied-port fixture')
        start_client()
        wait_for(lambda: 'remote port forwarding failed' in
                 docker('logs', CLIENT).stderr, 'occupied reverse port rejected', timeout=30)
        assert not probe(), 'Unexpected HTTP forwarding through occupied port'
        docker('restart', SERVER)
        wait_for(probe, 'reconnect after reverse port becomes available', timeout=120)
        docker('stop', '--time', '20', CLIENT)
        remove_client()

        # A valid but incorrect host public key must prevent all forwarding.
        server_python("from pathlib import Path; p=Path('/fixture/config'); "
                      "(p/'known_hosts').write_text('ssh-server '+(p/'id_ed25519.pub').read_text())")
        start_client()
        wait_for(lambda: 'Host key verification failed' in
                 docker('logs', CLIENT).stderr, 'mismatched server host key rejected', timeout=30)
        assert not probe(), 'Unexpected forwarding with wrong host key'
        remove_client()

        # A passphrase-protected key must stop before any SSH connection.
        server_python("from pathlib import Path; p=Path('/fixture/config'); "
                      "(p/'known_hosts').write_bytes((p/'known_hosts.good').read_bytes())")
        docker('exec', SERVER, 'ssh-keygen', '-p', '-P', '', '-N', 'disposable-test-only',
               '-f', '/fixture/config/id_ed25519')
        start_client()
        wait_for(lambda: docker('inspect', '--format', '{{.State.Status}}', CLIENT).stdout.strip()
                 == 'exited', 'encrypted key stops startup', timeout=30)
        assert docker('inspect', '--format', '{{.State.ExitCode}}', CLIENT).stdout.strip() == '1'
        assert not probe(), 'Unexpected forwarding with encrypted key'
        print('PASS: encrypted key rejected (exit 1)', flush=True)
        print('All local Docker integration checks passed.', flush=True)
    except Exception:
        for name in (CLIENT, SERVER):
            output = docker('logs', '--tail', '25', name, check=False)
            print(f'{name}:\n{output.stdout}\n{output.stderr}', flush=True)
        raise
    finally:
        remove_client()
        docker('rm', '-f', SERVER, check=False)
        docker('volume', 'rm', VOLUME, check=False)
        docker('network', 'rm', NETWORK, check=False)


if __name__ == '__main__':
    main()
