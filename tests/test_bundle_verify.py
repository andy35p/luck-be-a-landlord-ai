import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from verify_live_bundle import verify


class BundleVerifyTests(unittest.TestCase):
    def manifest(self,root,files):
        (root/'package_manifest.json').write_text(json.dumps({'format':1,'purpose':'local-test-only','files':files}))

    def test_modified_missing_and_unexpected_code_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'main.py'; source.write_bytes(b'original')
            self.manifest(root,{'main.py':hashlib.sha256(b'original').hexdigest()})
            self.assertTrue(verify(root)['passed'])
            source.write_bytes(b'changed'); self.assertFalse(verify(root)['passed'])
            source.write_bytes(b'original'); (root/'json.py').write_text('shadow import')
            self.assertFalse(verify(root)['passed'])
            self.manifest(root,{'missing.py':'abc'})
            with self.assertRaises(FileNotFoundError): verify(root)

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('../outside','/outside','C:/outside','..\\outside'):
                self.manifest(root,{name:'abc'})
                with self.subTest(name=name), self.assertRaises(ValueError): verify(root)
