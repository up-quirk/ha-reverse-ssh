import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'reverse_ssh' / 'tunnel.py'
spec = importlib.util.spec_from_file_location('tunnel', MODULE)
tunnel = importlib.util.module_from_spec(spec)
if MODULE.exists():
    spec.loader.exec_module(tunnel)


class TunnelTests(unittest.TestCase):
    def options(self, **changes):
        return dict(ssh_host='vpn.example.org', ssh_port=22, ssh_user='ha-tunnel',
                    remote_bind_address='127.0.0.1', remote_port=18123,
                    target_host='homeassistant', target_port=8123,
                    use_autossh=True, **changes)

    def test_ssh_arguments_enforce_host_identity_and_forward(self):
        args = tunnel.command(tunnel.validate(self.options()), Path('/data/ssh'))
        self.assertEqual(args[:3], ['autossh', '-M', '0'])
        self.assertIn('StrictHostKeyChecking=yes', args)
        self.assertIn('ExitOnForwardFailure=yes', args)
        self.assertIn('BatchMode=yes', args)
        self.assertIn('127.0.0.1:18123:homeassistant:8123', args)
        self.assertEqual(args[-1], 'vpn.example.org')

    def test_plain_ssh_mode(self):
        opts = self.options()
        opts['use_autossh'] = False
        self.assertEqual(tunnel.command(tunnel.validate(opts), Path('/data/ssh'))[0], 'ssh')

    def test_rejects_unsafe_hosts_ports_and_wrong_types(self):
        for field, value in [('ssh_host', '-oProxyCommand=evil'),
                             ('ssh_host', 'host\nother'), ('target_host', 'x:y'),
                             ('ssh_user', '-root'), ('remote_port', 0),
                             ('ssh_port', True), ('target_port', 65536),
                             ('use_autossh', 'false'), ('remote_bind_address', '*')]:
            with self.subTest(field=field, value=value):
                opts = self.options()
                opts[field] = value
                with self.assertRaises(ValueError):
                    tunnel.validate(opts)

    def test_ipv6_forward_is_bracketed(self):
        opts = self.options()
        opts.update(remote_bind_address='::1', target_host='2001:db8::1')
        self.assertIn('[::1]:18123:[2001:db8::1]:8123',
                      tunnel.command(tunnel.validate(opts), Path('/data/ssh')))

    def test_credentials_are_copied_without_modifying_uploads(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp) / 'config', Path(tmp) / 'runtime'
            source.mkdir()
            for name in ('id_ed25519', 'known_hosts'):
                (source / name).write_bytes(b'line1\r\nline2\r\n')
            tunnel.prepare_credentials(source, dest)
            self.assertEqual((dest / 'id_ed25519').read_bytes(), b'line1\nline2\n')
            self.assertEqual((source / 'id_ed25519').read_bytes(), b'line1\r\nline2\r\n')
            if os.name == 'posix':
                self.assertEqual((dest / 'id_ed25519').stat().st_mode & 0o777, 0o600)

    def test_missing_and_empty_credentials_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'config'
            source.mkdir()
            with self.assertRaises(ValueError):
                tunnel.prepare_credentials(source, Path(tmp) / 'runtime')
            (source / 'id_ed25519').write_text('')
            (source / 'known_hosts').write_text('host key')
            with self.assertRaises(ValueError):
                tunnel.prepare_credentials(source, Path(tmp) / 'runtime')

    def test_setup_waits_for_both_nonempty_files_then_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp) / 'config', Path(tmp) / 'runtime'
            source.mkdir()
            (source / 'id_ed25519').write_text('private-test-only')
            (source / 'known_hosts').write_text('')
            class Stop:
                waits = 0
                def is_set(self):
                    return False
                def wait(self, seconds):
                    self.waits += 1
                    (source / 'known_hosts').write_text('host public-test-only')
            stop = Stop()
            with self.assertLogs('reverse_ssh', level='INFO') as logs:
                self.assertTrue(tunnel.wait_for_credentials(source, dest, stop))
            self.assertEqual(stop.waits, 1)
            self.assertEqual((dest / 'known_hosts').read_text(), 'host public-test-only\n')
            self.assertNotIn('private-test-only', str(logs.output))

    def test_setup_wait_is_interruptible_and_does_not_create_keys(self):
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp) / 'config', Path(tmp) / 'runtime'
            source.mkdir()
            stop = threading.Event()
            with patch.object(stop, 'wait', side_effect=lambda _: stop.set()), \
                 self.assertLogs('reverse_ssh', level='INFO'):
                self.assertFalse(tunnel.wait_for_credentials(source, dest, stop))
            self.assertEqual(list(source.iterdir()), [])
            self.assertFalse(dest.exists())

    @unittest.skipUnless(os.name == 'posix', 'Symlink creation requires privileges on Windows')
    def test_symlink_credentials_rejected(self):
        for linked in ('id_ed25519', 'known_hosts'):
            with self.subTest(linked=linked), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / 'config'
                source.mkdir()
                external = Path(tmp) / 'external'
                external.write_text('must not be read')
                for name in ('id_ed25519', 'known_hosts'):
                    if name == linked:
                        (source / name).symlink_to(external)
                    else:
                        (source / name).write_text('nonempty')
                with self.assertRaises(ValueError):
                    tunnel.prepare_credentials(source, Path(tmp) / 'runtime')

    def test_invalid_key_and_keycheck_timeout_prevent_launch(self):
        for result in ('invalid', 'timeout'):
            with self.subTest(result=result):
                kwargs = ({'return_value': tunnel.subprocess.CompletedProcess([], 1)}
                          if result == 'invalid' else
                          {'side_effect': tunnel.subprocess.TimeoutExpired('ssh-keygen', 10)})
                with patch.object(Path, 'read_text', return_value=json.dumps(self.options())), \
                     patch.object(tunnel, 'wait_for_credentials', return_value=True), \
                     patch.object(tunnel.signal, 'signal'), \
                     patch.object(tunnel.os, 'umask'), \
                     patch.object(tunnel.subprocess, 'run', **kwargs), \
                     patch.object(tunnel.subprocess, 'Popen', side_effect=AssertionError('Must not connect')), \
                     self.assertLogs('reverse_ssh', level='ERROR'):
                    self.assertEqual(tunnel.main(), 1)

    def test_stop_during_retry_prevents_another_connection(self):
        import threading
        stop = threading.Event()
        class Child:
            def poll(self):
                stop.set()
                return 255
        starts = []
        def spawn(*args, **kwargs):
            starts.append(1)
            return Child()
        with patch.object(tunnel.subprocess, 'Popen', side_effect=spawn):
            tunnel.supervise(['ssh'], stop, retry_seconds=0)
        self.assertEqual(len(starts), 1)

    def test_unresponsive_child_is_killed_and_reaped(self):
        import threading
        stop = threading.Event()
        class Child:
            killed, reaped = False, False
            def poll(self):
                stop.set()
                return None
            def terminate(self):
                pass
            def wait(self, timeout=None):
                if timeout is not None:
                    raise tunnel.subprocess.TimeoutExpired('ssh', timeout)
                self.reaped = True
                return 0
            def kill(self):
                self.killed = True
        child = Child()
        with patch.object(tunnel.subprocess, 'Popen', return_value=child):
            tunnel.supervise(['ssh'], stop, poll_seconds=0)
        self.assertTrue(child.killed)
        self.assertTrue(child.reaped)

    def test_process_exit_reconnects_and_stop_terminates_child(self):
        # Process creation is the external boundary; actual launcher controls retry.
        import threading
        stop = threading.Event()
        class Child:
            def __init__(self, first):
                self.first, self.terminated = first, False
            def poll(self):
                if self.first:
                    return 255
                stop.set()
                return None
            def terminate(self):
                self.terminated = True
            def wait(self, timeout=None):
                return 0
        children = []
        def spawn(*args, **kwargs):
            child = Child(not children)
            children.append(child)
            return child
        with patch.object(tunnel.subprocess, 'Popen', side_effect=spawn):
            tunnel.supervise(['ssh'], stop, retry_seconds=0, poll_seconds=0)
        self.assertEqual(len(children), 2)
        self.assertTrue(children[1].terminated)


if __name__ == '__main__':
    unittest.main()
