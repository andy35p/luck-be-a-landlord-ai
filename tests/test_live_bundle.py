import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.build_live_bundle import FILES, build


class LiveBundleTests(unittest.TestCase):
    def test_explicit_profiles_keep_binary_and_manifest_paired(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); old=self.fixture(root)
            source=root/'integrations/collector_v07';source.mkdir()
            binary=root/'new.dll';binary.write_bytes(b'new-verified-test-binary')
            (source/'verified_build.json').write_text(json.dumps({'version':'0.7.0',
                'dll_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}))
            (source/'manifest.json').write_text(json.dumps({'Id':'LandlordResearch',
                'AssemblyPath':'LandlordResearch.dll','Metadata':{'Version':'0.7.0'}}))
            result=build(root,binary,root/'new.zip','0.7.0')
            self.assertEqual(result['collector_version'],'0.7.0')
            with self.assertRaises(ValueError):build(root,old,root/'mixed.zip','0.7.0')
            with self.assertRaises(ValueError):build(root,binary,root/'wrong.zip')
            with self.assertRaises(ValueError):build(root,binary,root/'unknown.zip','../collector_v07')

    def fixture(self, root):
        for name in FILES:
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture', encoding='utf-8')
        source = root/'integrations/collector_v05'
        source.mkdir(parents=True)
        binary = root/'verified.dll'
        binary.write_bytes(b'verified-test-binary')
        (source/'verified_build.json').write_text(json.dumps({'version':'0.5.0',
            'dll_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}))
        (source/'manifest.json').write_text(json.dumps({'Id':'LandlordResearch',
            'AssemblyPath':'LandlordResearch.dll','Metadata':{'Version':'0.5.0'}}))
        (root/'integrations/local_assistant_README.md').write_text('Local only')
        (root/'secret.env').write_text('must not ship')
        return binary

    def test_deterministic_allowlist_and_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); binary = self.fixture(root)
            a, b = root/'a.zip', root/'b.zip'
            manifest = build(root,binary,a); build(root,binary,b)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            with zipfile.ZipFile(a) as archive:
                self.assertEqual(set(archive.namelist()), set(manifest['files'])|{'package_manifest.json'})
                self.assertNotIn('secret.env',archive.namelist())
                for name, digest in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(),digest)
            with self.assertRaises(FileExistsError): build(root,binary,a)

    def test_unverified_binary_and_mismatched_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); binary=self.fixture(root); output=root/'bad.zip'
            wrong=root/'controlled.dll'; wrong.write_bytes(b'controlled-test')
            with self.assertRaises(ValueError): build(root,wrong,output)
            self.assertFalse(output.exists())
            (root/'integrations/collector_v05/manifest.json').write_text('{}')
            with self.assertRaises(ValueError): build(root,binary,output)
            self.assertFalse(output.exists())
