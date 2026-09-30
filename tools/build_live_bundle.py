"""Deterministic allowlisted local bundle; never installs or publishes it."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'resolve_live_python.ps1',
    'watch_live_advice.py', 'watch_live_advice.ps1', 'start_live_assistant.ps1', 'verify_live_bundle.py',
    'manage_live_install.py',
    'luck_agent/__init__.py', 'luck_agent/agents/__init__.py',
    'luck_agent/agents/live_advisor.py', 'luck_agent/agents/heuristic_agent.py',
    'luck_agent/env/__init__.py', 'luck_agent/env/action.py',
    'luck_agent/env/game_state.py', 'luck_agent/env/rule_engine.py',
    'luck_agent/evaluation/__init__.py', 'luck_agent/evaluation/live_observation.py',
    'luck_agent/evaluation/live_feed.py', 'luck_agent/evaluation/advice_display.py',
    'luck_agent/evaluation/live_run.py', 'luck_agent/legacy/__init__.py',
    'luck_agent/evaluation/live_item_scope.py',
    'luck_agent/evaluation/live_board.py', 'luck_agent/evaluation/live_collector_contract.py',
    'luck_agent/legacy/fast_env.py', 'luck_agent/legacy/catalog.json',
)


def build(root, dll, output, collector_version='0.5.0'):
    root, dll, output = Path(root), Path(dll), Path(output)
    profiles = {'0.5.0':'collector_v05', '0.7.0':'collector_v07'}
    if collector_version not in profiles:
        raise ValueError('Unsupported collector release profile')
    source = root/'integrations'/profiles[collector_version]
    expected = json.loads((source/'verified_build.json').read_text())
    if expected['version'] != collector_version:
        raise ValueError('Collector baseline version mismatch')
    binary = dll.read_bytes()
    if hashlib.sha256(binary).hexdigest().upper() != expected['dll_sha256'].upper():
        raise ValueError('Collector is not the verified production binary')
    payload = {name: (root/name).read_bytes() for name in FILES}
    payload['collector/LandlordResearch.dll'] = binary
    payload['collector/manifest.json'] = (source/'manifest.json').read_bytes()
    collector = json.loads(payload['collector/manifest.json'])
    if (collector.get('Id') != 'LandlordResearch' or collector.get('AssemblyPath') != 'LandlordResearch.dll'
            or collector.get('Metadata', {}).get('Version') != expected['version']):
        raise ValueError('Collector manifest does not match the verified version')
    payload['README.md'] = (root/'integrations/local_assistant_README.md').read_bytes()
    manifest = {'format': 1, 'purpose': 'local-test-only', 'collector_version': expected['version'],
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payload.items())}}
    payload['package_manifest.json'] = (json.dumps(manifest, sort_keys=True, indent=2)+'\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation keeps earlier artifacts intact.
    with output.open('xb') as stream, zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--collector-dll', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--collector-version', choices=('0.5.0','0.7.0'), default='0.5.0')
    args = parser.parse_args()
    manifest = build(ROOT, args.collector_dll, args.output, args.collector_version)
    print(json.dumps({'output': str(args.output), 'files': len(manifest['files']),
                      'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
