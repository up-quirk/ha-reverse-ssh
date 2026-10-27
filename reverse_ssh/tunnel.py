"""Noninteractive reverse SSH tunnel. Never logs configuration or credentials."""
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import threading

LOG = logging.getLogger('reverse_ssh')


def host(value):
    if not isinstance(value, str) or not value or len(value) > 253:
        raise ValueError('Host must be an IP address or DNS name')
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        if not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', p)
                   for p in value.rstrip('.').split('.')):
            raise ValueError('Invalid host') from None
        return value


def validate(options):
    result = dict(options)
    for field in ('ssh_host', 'target_host'):
        result[field] = host(options.get(field))
    user = options.get('ssh_user')
    if not isinstance(user, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}', user):
        raise ValueError('Invalid SSH username')
    for field in ('ssh_port', 'remote_port', 'target_port'):
        value = options.get(field)
        if type(value) is not int or not 1 <= value <= 65535:
            raise ValueError(f'{field} must be an integer between 1 and 65535')
    if type(options.get('use_autossh')) is not bool:
        raise ValueError('use_autossh must be a boolean')
    try:
        ipaddress.ip_address(options.get('remote_bind_address'))
    except (ValueError, TypeError):
        raise ValueError('remote_bind_address must be an explicit IP address') from None
    return result


def prepare_credentials(source, dest):
    # Validate both before writing; a read-only upload mount is sufficient.
    contents = {}
    for name in ('id_ed25519', 'known_hosts'):
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Upload {name} into the app configuration folder')
        data = path.read_bytes()
        if not data.strip() or len(data) > 1024 * 1024:
            raise ValueError(f'{name} must be nonempty and at most 1 MiB')
        contents[name] = data.replace(b'\r\n', b'\n')
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(dest, 0o700)
    for name, data in contents.items():
        path = dest / name
        # Runtime directory is private to the container, never the shared mount.
        path.write_bytes(data if data.endswith(b'\n') else data + b'\n')
        os.chmod(path, 0o600)


def bracket(value):
    return f'[{value}]' if ':' in value else value


def command(options, credentials):
    forward = (f"{bracket(options['remote_bind_address'])}:{options['remote_port']}:"
               f"{bracket(options['target_host'])}:{options['target_port']}")
    args = ['autossh', '-M', '0'] if options['use_autossh'] else ['ssh']
    args += ['-F', '/dev/null', '-N', '-T', '-i', str(credentials / 'id_ed25519'),
             '-p', str(options['ssh_port']), '-l', options['ssh_user']]
    for setting in ('BatchMode=yes', 'IdentitiesOnly=yes', 'IdentityAgent=none',
                    'StrictHostKeyChecking=yes', 'GlobalKnownHostsFile=/dev/null',
                    f'UserKnownHostsFile={credentials / "known_hosts"}',
                    'ExitOnForwardFailure=yes', 'ServerAliveInterval=30',
                    'ServerAliveCountMax=3', 'ConnectTimeout=15',
                    'ConnectionAttempts=1', 'LogLevel=ERROR'):
        args += ['-o', setting]
    return args + ['-R', forward, options['ssh_host']]


def supervise(args, stop, retry_seconds=10, poll_seconds=0.5):
    env = dict(os.environ, AUTOSSH_GATETIME='0', AUTOSSH_POLL='30')
    while not stop.is_set():
        LOG.info('Starting tunnel client')
        child = subprocess.Popen(args, env=env)
        try:
            while child.poll() is None and not stop.is_set():
                stop.wait(poll_seconds)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        if not stop.is_set():
            LOG.warning('Tunnel client exited; retrying in %s seconds', retry_seconds)
            stop.wait(retry_seconds)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    os.umask(0o077)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        options = validate(json.loads(Path('/data/options.json').read_text()))
        credentials = Path('/run/reverse-ssh')
        prepare_credentials(Path('/config'), credentials)
        # Parse the key locally: fail before repeatedly trying an invalid or
        # passphrase-protected key. Never print key contents or its public key.
        check = subprocess.run(['ssh-keygen', '-y', '-P', '', '-f',
                                str(credentials / 'id_ed25519')],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, check=False)
        if check.returncode:
            raise ValueError('SSH key is invalid or requires a passphrase')
        supervise(command(options, credentials), stop)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        # OSError text may include paths, but never file content/options.
        LOG.error('Cannot start tunnel: %s', error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
