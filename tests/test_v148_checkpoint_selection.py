"""V148 episode isolation, leakage guards, lock and audit invariants."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.v148_split_coverage import create_split_manifest,load_split_data,fit_scaler

OUT=ROOT/'logs/v148-checkpoint-selection'
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

class V148SplitTests(unittest.TestCase):
    def test_episode_split_is_deterministic_disjoint_and_hashed(self):
        a=create_split_manifest(148001,name='primary-a');b=create_split_manifest(148001,name='primary-a')
        self.assertEqual(a,b);self.assertEqual(len(a['fit_episodes']),24);self.assertEqual(len(a['selection_episodes']),8)
        self.assertFalse(set(a['fit_episodes'])&set(a['selection_episodes']))
        self.assertEqual(set(a['fit_episodes'])|set(a['selection_episodes']),set(range(9000,9032)))
        self.assertEqual(len(a['split_hash']),64);self.assertEqual(a['test_access'],'FORBIDDEN')

    def test_train_mode_opens_only_train_shards_and_scaler_is_fit_only(self):
        manifest=create_split_manifest(148001,name='primary-a');opened=[]
        import tools.v148_split_coverage as module
        original=module._digest
        def monitored(path):opened.append(Path(path).name);return original(path)
        with patch.object(module,'_digest',side_effect=monitored):data=load_split_data(manifest,mode='train')
        self.assertTrue(opened);self.assertTrue(all(name.startswith('train-') for name in opened))
        scaler=data['scaler'];self.assertEqual(scaler['fit_episodes'],manifest['fit_episodes'])
        self.assertEqual(scaler['samples'],len(data['fit_raw']));self.assertTrue(scaler['selection_excluded'])
        altered=list(data['selection_raw']);altered[0]=dict(altered[0],scalars=[10**9]*8)
        self.assertEqual(fit_scaler(data['fit_raw'],manifest),scaler)

    def test_audit_requires_complete_immutable_choice_lock(self):
        manifest=create_split_manifest(148001,name='primary-a');data=load_split_data(manifest,mode='train')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'lock.json';path.write_text('{}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'not locked'):load_split_data(manifest,mode='audit',scaler=data['scaler'],lock_path=path)
            choices={str(seed):{'ce_selected_update':500} for seed in manifest['training_seeds']}
            path.write_text(json.dumps({'splits':{'primary-a':{'split_hash':manifest['split_hash'],'choices':choices}}}),encoding='utf-8')
            opened=[]
            import tools.v148_split_coverage as module
            original=module._digest
            def monitored(p):opened.append(Path(p).name);return original(p)
            with patch.object(module,'_digest',side_effect=monitored):audit=load_split_data(manifest,mode='audit',scaler=data['scaler'],lock_path=path)
            self.assertTrue(audit['audit']);self.assertTrue(all(name.startswith('validation-') for name in opened))
            self.assertFalse(any(name.startswith('test-') for name in opened))

    def test_frozen_config_matches_derived_splits(self):
        config=read(ROOT/'configs/v148_checkpoint_selection.json')
        for spec in config['splits']:
            actual=create_split_manifest(spec['split_seed'],name=spec['name'],training_seeds=tuple(spec['training_seeds']))
            self.assertEqual(actual['fit_episodes'],spec['fit_episode_ids'])
            self.assertEqual(actual['selection_episodes'],spec['selection_episode_ids'])
        self.assertEqual(config['primary_selection_metric'],'SELECTION symbol cross entropy')
        self.assertEqual(config['online_smoke'],'NOT APPLICABLE')

    def test_lock_tie_break_and_gradient_contract(self):
        lock=OUT/'checkpoint_choices.lock.json'
        if not lock.exists():return
        config=read(ROOT/'configs/v148_checkpoint_selection.json');value=read(lock)
        for spec in config['splits']:
            for seed in spec['training_seeds']:
                run=read(OUT/'training_curves'/spec['name']/f'seed-{seed}.json')
                expected=min(run['checkpoints'].values(),key=lambda x:(x['selection']['symbol']['ce'],x['update']))
                choice=value['splits'][spec['name']]['choices'][str(seed)]
                self.assertEqual(choice['ce_selected_update'],expected['update'])
                self.assertEqual(run['selection_gradient_steps'],0)
                self.assertEqual(run['development_validation_access'],'NOT OPENED')

    def test_post_audit_contract(self):
        analysis=OUT/'analysis.json'
        if not analysis.exists():return
        result=read(analysis);raw=read(OUT/'audit_raw.json');frozen=read(OUT/'frozen_verification.json')
        self.assertEqual(result['test_access'],'FORBIDDEN');self.assertEqual(result['online_smoke'],'NOT APPLICABLE')
        self.assertTrue(raw['audit_started_after_lock']);self.assertFalse(frozen['test_shards_opened'])
        self.assertFalse(frozen['v128_manifest_opened']);self.assertEqual(frozen['changed'],[])

if __name__=='__main__':unittest.main()
