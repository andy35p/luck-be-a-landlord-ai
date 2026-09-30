"""Read-only installed PCK compatibility audit; emits facts/hashes, not game source."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def read_resource(pck,resource='res://Main.tscn'):
    with Path(pck).open('rb') as stream:
        if stream.read(4)!=b'GDPC': raise ValueError('Not a Godot pack')
        version=struct.unpack('<I',stream.read(4))[0]
        if version!=1: raise ValueError('Only the locally inspected Godot pack version 1 is supported')
        stream.seek(0x54); count=struct.unpack('<I',stream.read(4))[0]
        if count>100000: raise ValueError('Unreasonable pack entry count')
        target=None
        for _ in range(count):
            length=struct.unpack('<I',stream.read(4))[0]
            if length>65536: raise ValueError('Unreasonable resource name')
            name=stream.read(length).rstrip(b'\0').decode('utf-8')
            offset,size=struct.unpack('<QQ',stream.read(16)); stream.read(16)
            if name==resource: target=(offset,size)
        if target is None: raise ValueError('Requested resource not found in this pack')
        offset,size=target
        if size>10*1024*1024 or offset+size>Path(pck).stat().st_size: raise ValueError('Invalid scene bounds')
        stream.seek(offset); return stream.read(size)


def audit(pck,reference=None):
    raw=read_resource(pck); source=raw.decode('utf-8').replace('\r\n','\n')
    start=source.index('func check_for_allowed_function(')
    end=source.index('func get_appended_steam_id(',start)
    validator=source[start:end]
    constrained=('for f in []:' in validator and 'func _init():' in validator
                 and 'base_mod_fields.keys().has(key)' in validator and source.count('malicious_mod(')>1)
    return {'scope':'Read-only facts about installed text scene; no loader bypass or Workshop upload',
        'main_scene_sha256':hashlib.sha256(raw).hexdigest(),
        'reference_matches':raw==Path(reference).read_bytes() if reference else None,
        'has_mod_validator': 'func malicious_mod(' in validator,
        'empty_function_allowlist':'for f in []:' in validator,
        'init_exception_present':'func _init():' in validator,
        'rejects_unknown_assignments':'base_mod_fields.keys().has(key)' in validator,
        'validator_call_sites':source.count('malicious_mod(')-1,
        'implication':('Installed loader restrictions block current polling/file-I/O/overlay implementation through the ordinary mod entry'
                       if constrained else 'Loader surface differs; manual compatibility review required')}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('pck',type=Path)
    parser.add_argument('--reference',type=Path); parser.add_argument('--output',type=Path)
    args=parser.parse_args(); result=audit(args.pck,args.reference)
    text=json.dumps(result,indent=2)+'\n'
    if args.output: args.output.write_text(text,encoding='utf-8')
    print(text)


if __name__=='__main__': main()
