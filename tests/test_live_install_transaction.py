import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from manage_live_install import install, rollback, tree_hashes, installation_lock, inspect_transaction, recover
import manage_live_install


class InstallTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name).resolve(); self.game=root/'game'; self.game.mkdir()
        (self.game/'Luck be a Landlord.exe').write_bytes(b'fixture')
        core=self.game/'SlotWeave/core'; core.mkdir(parents=True)
        (core/'SlotWeave.dll').write_bytes(b'fixture')
        self.bundle=root/'bundle'; source=self.bundle/'collector'; source.mkdir(parents=True)
        (source/'LandlordResearch.dll').write_bytes(b'new')
        (source/'manifest.json').write_text(json.dumps({'Id':'LandlordResearch','AssemblyPath':'LandlordResearch.dll'}))
        files={p.relative_to(self.bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        (self.bundle/'package_manifest.json').write_text(json.dumps({'format':1,'purpose':'local-test-only','files':files}))
        self.target=self.game/'SlotWeave/mods/LandlordResearch'

    def add_old(self):
        self.target.mkdir(parents=True)
        (self.target/'LandlordResearch.dll').write_bytes(b'old')
        (self.target/'manifest.json').write_text('old manifest')
        (self.target/'user-config.json').write_text('preserve')

    def test_existing_plugin_roundtrip_and_dry_run(self):
        self.add_old(); before=tree_hashes(self.target)
        self.assertFalse(install(self.bundle,self.game,running=lambda:False)['applied'])
        self.assertEqual(tree_hashes(self.target),before)
        self.assertFalse((self.game/'SlotWeave/research-backups').exists())
        result=install(self.bundle,self.game,apply=True,running=lambda:False)
        self.assertEqual((self.target/'user-config.json').read_text(),'preserve')
        receipt=Path(result['receipt'])
        self.assertEqual(tree_hashes(receipt.parent/'previous'),before)
        rollback(receipt,self.game,apply=True,running=lambda:False)
        self.assertEqual(tree_hashes(self.target),before)
        self.assertTrue((receipt.parent/'removed-install/LandlordResearch.dll').exists())

    def test_new_plugin_rollback_removes_only_its_directory_by_archiving(self):
        receipt=install(self.bundle,self.game,apply=True,running=lambda:False)['receipt']
        rollback(receipt,self.game,apply=True,running=lambda:False)
        self.assertFalse(self.target.exists())
        self.assertTrue((Path(receipt).parent/'removed-install').is_dir())

    def test_running_game_and_changed_plugin_refused(self):
        self.add_old(); before=tree_hashes(self.target)
        with self.assertRaises(RuntimeError): install(self.bundle,self.game,apply=True,running=lambda:True)
        self.assertEqual(tree_hashes(self.target),before)
        receipt=install(self.bundle,self.game,apply=True,running=lambda:False)['receipt']
        (self.target/'user-config.json').write_text('new user edit')
        with self.assertRaises(ValueError): rollback(receipt,self.game,apply=True,running=lambda:False)
        self.assertEqual((self.target/'user-config.json').read_text(),'new user edit')

    def test_failed_replacement_restores_original(self):
        self.add_old(); before=tree_hashes(self.target); original=Path.rename
        def rename(path,destination):
            if path.name=='staged': raise OSError('simulated replacement failure')
            return original(path,destination)
        with patch.object(Path,'rename',rename), self.assertRaises(OSError):
            install(self.bundle,self.game,apply=True,running=lambda:False)
        self.assertEqual(tree_hashes(self.target),before)

    def test_changed_backup_refused(self):
        self.add_old(); receipt=Path(install(self.bundle,self.game,apply=True,running=lambda:False)['receipt'])
        (receipt.parent/'previous/LandlordResearch.dll').write_bytes(b'corrupt')
        with self.assertRaises(ValueError): rollback(receipt,self.game,apply=True,running=lambda:False)
        self.assertEqual((self.target/'LandlordResearch.dll').read_bytes(),b'new')

    def test_concurrent_operation_refused_and_lock_released(self):
        self.add_old(); before=tree_hashes(self.target)
        with installation_lock(self.game):
            with self.assertRaises(RuntimeError):
                install(self.bundle,self.game,apply=True,running=lambda:False)
        self.assertEqual(tree_hashes(self.target),before)
        self.assertTrue(install(self.bundle,self.game,apply=True,running=lambda:False)['applied'])

    def test_abandoned_prepared_transaction_blocks_new_install(self):
        folder=self.game/'SlotWeave/research-backups/unfinished'; folder.mkdir(parents=True)
        (folder/'receipt.json').write_text(json.dumps({'status':'prepared'}))
        with self.assertRaises(RuntimeError): install(self.bundle,self.game,apply=True,running=lambda:False)
        self.assertFalse(self.target.exists())

    def test_interrupted_install_recovers_each_switch_phase(self):
        self.add_old(); before=tree_hashes(self.target)
        original_write=manage_live_install.write_receipt
        original_rename=Path.rename
        for phase in ('not_switched','original_archived','replacement_in_place'):
            def write(folder,receipt):
                if phase=='replacement_in_place' and receipt['status']=='installed': raise SystemExit('power-loss simulation')
                original_write(folder,receipt)
                if phase=='not_switched' and receipt['status']=='prepared': raise SystemExit('power-loss simulation')
            def rename(path,destination):
                if phase=='original_archived' and path.name=='staged': raise SystemExit('power-loss simulation')
                return original_rename(path,destination)
            with self.subTest(phase=phase), patch.object(manage_live_install,'write_receipt',write), patch.object(Path,'rename',rename):
                with self.assertRaises(SystemExit): install(self.bundle,self.game,apply=True,running=lambda:False)
            receipt=next(p for p in (self.game/'SlotWeave/research-backups').glob('*/receipt.json')
                         if json.loads(p.read_text())['status']=='prepared')
            self.assertEqual(inspect_transaction(receipt,self.game)['phase'],phase)
            result=recover(receipt,self.game,apply=True,running=lambda:False)
            self.assertTrue(result['restored']); self.assertEqual(tree_hashes(self.target),before)

    def test_interrupted_first_install_recovers_absent_target(self):
        original_write=manage_live_install.write_receipt
        def write(folder,receipt):
            if receipt['status']=='installed': raise SystemExit('interruption')
            original_write(folder,receipt)
        with patch.object(manage_live_install,'write_receipt',write), self.assertRaises(SystemExit):
            install(self.bundle,self.game,apply=True,running=lambda:False)
        receipt=next((self.game/'SlotWeave/research-backups').glob('*/receipt.json'))
        self.assertEqual(inspect_transaction(receipt,self.game)['phase'],'replacement_in_place')
        recover(receipt,self.game,apply=True,running=lambda:False)
        self.assertFalse(self.target.exists())

    def test_interrupted_evidence_conflict_refuses_recovery(self):
        self.add_old(); path=Path(install(self.bundle,self.game,apply=True,running=lambda:False)['receipt'])
        receipt=json.loads(path.read_text()); receipt['status']='prepared'
        path.write_text(json.dumps(receipt))
        (path.parent/'previous/LandlordResearch.dll').write_bytes(b'changed backup')
        self.assertFalse(inspect_transaction(path,self.game)['recoverable'])
        current=tree_hashes(self.target)
        with self.assertRaises(ValueError): recover(path,self.game,apply=True,running=lambda:False)
        self.assertEqual(tree_hashes(self.target),current)

    def test_rollback_interruptions_resume_without_losing_original(self):
        self.add_old(); before=tree_hashes(self.target)
        original_write=manage_live_install.write_receipt; original_rename=Path.rename
        for boundary in ('journal','archive','restore','finish'):
            path=Path(install(self.bundle,self.game,apply=True,running=lambda:False)['receipt'])
            def write(folder,receipt):
                if boundary=='finish' and receipt['status']=='rolled_back': raise SystemExit('interrupted')
                original_write(folder,receipt)
                if boundary=='journal' and receipt['status']=='rollback_prepared': raise SystemExit('interrupted')
            def rename(source,destination):
                value=original_rename(source,destination)
                if ((boundary=='archive' and Path(destination).name=='removed-install') or
                    (boundary=='restore' and source.name=='previous')): raise SystemExit('interrupted')
                return value
            with self.subTest(boundary=boundary), patch.object(manage_live_install,'write_receipt',write), patch.object(Path,'rename',rename):
                with self.assertRaises(SystemExit): rollback(path,self.game,apply=True,running=lambda:False)
            self.assertTrue(inspect_transaction(path,self.game)['recoverable'])
            recover(path,self.game,apply=True,running=lambda:False)
            self.assertEqual(tree_hashes(self.target),before)
            self.assertEqual(json.loads(path.read_text())['status'],'rolled_back')

    def test_recovery_itself_can_resume_after_archiving(self):
        self.add_old(); before=tree_hashes(self.target)
        path=Path(install(self.bundle,self.game,apply=True,running=lambda:False)['receipt'])
        receipt=json.loads(path.read_text()); receipt['status']='prepared'; path.write_text(json.dumps(receipt))
        original=Path.rename
        def rename(source,destination):
            value=original(source,destination)
            if Path(destination).name=='recovery-installed': raise SystemExit('interrupted recovery')
            return value
        with patch.object(Path,'rename',rename), self.assertRaises(SystemExit):
            recover(path,self.game,apply=True,running=lambda:False)
        self.assertEqual(inspect_transaction(path,self.game)['phase'],'restore_original')
        recover(path,self.game,apply=True,running=lambda:False)
        self.assertEqual(tree_hashes(self.target),before)

    def test_first_install_rollback_interruption_preserves_absence(self):
        path=Path(install(self.bundle,self.game,apply=True,running=lambda:False)['receipt'])
        original=Path.rename
        def rename(source,destination):
            value=original(source,destination)
            if Path(destination).name=='removed-install': raise SystemExit('interrupted')
            return value
        with patch.object(Path,'rename',rename), self.assertRaises(SystemExit):
            rollback(path,self.game,apply=True,running=lambda:False)
        recover(path,self.game,apply=True,running=lambda:False)
        self.assertFalse(self.target.exists())
