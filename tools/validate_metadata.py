"""Repository structural checks; not a replacement for Supervisor validation."""
import importlib.util
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'reverse_ssh'


def main():
    config = yaml.safe_load((APP / 'config.yaml').read_text(encoding='utf-8'))
    repo = yaml.safe_load((ROOT / 'repository.yaml').read_text(encoding='utf-8'))
    for key in ('name', 'version', 'slug', 'description', 'arch', 'options', 'schema'):
        assert key in config, f'Missing {key}'
    assert isinstance(config['version'], str)
    assert config['arch'] == ['amd64', 'aarch64']
    assert set(config['options']) == set(config['schema'])
    assert repo['url'] == config['url']
    for locale in ('en', 'de'):
        translation = yaml.safe_load((APP / 'translations' / f'{locale}.yaml').read_text(encoding='utf-8'))
        assert set(translation['configuration']) == set(config['options'])
    spec = importlib.util.spec_from_file_location('tunnel', APP / 'tunnel.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    example = dict(config['options'], ssh_host='vpn.example.org')
    module.validate(example)
    assert config['map'] == [{'type': 'app_config', 'read_only': True}]
    assert not any(config.get(key) for key in ('host_network', 'full_access', 'docker_api',
                                             'hassio_api', 'homeassistant_api', 'privileged'))
    for file in ROOT.rglob('*.y*ml'):
        if '.git' not in file.parts:
            yaml.safe_load(file.read_text(encoding='utf-8'))
    print('Metadata structure, translations, default options and YAML syntax: OK')


if __name__ == '__main__':
    main()
