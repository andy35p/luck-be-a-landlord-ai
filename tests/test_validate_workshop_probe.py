from pathlib import Path
import tempfile
import unittest

from tools.validate_workshop_probe import validate_package, validate_script


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "integrations/workshop_probe/package"
PCK = Path(r"D:\SteamLibrary\steamapps\common\Luck be a Landlord\Luck be a Landlord.pck")


@unittest.skipUnless(PCK.is_file(), "installed game pack is required")
class WorkshopProbeValidatorTests(unittest.TestCase):
    def test_package_matches_installed_static_contract(self):
        result = validate_package(PACKAGE, PCK)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(set(result["scripts"]), {"mouse.gd", "cheese.gd"})

    def test_rejects_unsupported_constructs(self):
        allowed = {"mod_type", "type"}
        mutations = {
            "call.gd": 'extends "res://Mod Data.gd"\nfunc _init():\n\tprint("x")\n',
            "field.gd": 'extends "res://Mod Data.gd"\nfunc _init():\n\tunknown = 1\n',
            "quote.gd": 'extends "res://Mod Data.gd\nfunc _init():\n\ttype = "mouse"\n',
            "mixed.gd": 'extends "res://Mod Data.gd"\nfunc _init():\n\ttype = "mouse"\n    mod_type = "existing_symbol"\n',
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in mutations.items():
                path = root / name
                path.write_text(source, encoding="utf-8")
                self.assertTrue(validate_script(path, allowed), name)
