"""Local collector install/rollback with retained originals; never touches saves."""
import argparse
from contextlib import contextmanager
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from verify_live_bundle import verify


def game_running():
    if os.name != 'nt': raise RuntimeError('Windows required for process checks')
    result=subprocess.run(['tasklist','/FI','IMAGENAME eq Luck be a Landlord.exe','/FO','CSV','/NH'],
                          capture_output=True,text=True,check=True)
    return any(row and row[0].lower()=='luck be a landlord.exe'
               for row in csv.reader(io.StringIO(result.stdout)))


def target_for(game):
    game=Path(game).resolve()
    if not (game/'Luck be a Landlord.exe').is_file(): raise ValueError('Game executable missing')
    if not (game/'SlotWeave/core/SlotWeave.dll').is_file(): raise ValueError('Install compatible SlotWeave first')
    target=game/'SlotWeave/mods/LandlordResearch'
    if target.resolve()!=target: raise ValueError('Redirected plugin path refused')
    if target.exists() and not target.is_dir(): raise ValueError('Plugin target is not a directory')
    return game,target


def tree_hashes(root):
    root=Path(root)
    if root.resolve()!=root.absolute(): raise ValueError('Redirected plugin directory refused')
    if not root.exists(): return None
    if not root.is_dir(): raise ValueError('Plugin evidence must be a directory')
    result={}
    for path in sorted(root.rglob('*')):
        if path.resolve()!=path.absolute(): raise ValueError('Redirected plugin contents refused')
        if path.is_file(): result[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def write_receipt(directory, receipt):
    stage=directory/'receipt.tmp'
    stage.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    os.replace(stage,directory/'receipt.json')


@contextmanager
def installation_lock(game):
    game,_=target_for(game)
    folder=game/'SlotWeave/research-backups'
    if folder.resolve()!=folder: raise ValueError('Redirected backup path refused')
    folder.mkdir(parents=True,exist_ok=True)
    lock=folder/'install.lock'
    if lock.resolve()!=lock: raise ValueError('Redirected lock path refused')
    with lock.open('a+b') as stream:
        stream.seek(0,2)
        if stream.tell()==0: stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            try: msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc: raise RuntimeError('Another installation operation is active') from exc
            try: yield
            finally:
                stream.seek(0); msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            try: fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc: raise RuntimeError('Another installation operation is active') from exc
            try: yield
            finally: fcntl.flock(stream,fcntl.LOCK_UN)


def install(bundle,game,*,apply=False,running=game_running):
    if not apply: return _install(bundle,game,apply=False,running=running)
    with installation_lock(game):
        folder=Path(game).resolve()/'SlotWeave/research-backups'
        for receipt in folder.glob('*/receipt.json'):
            if json.loads(receipt.read_text(encoding='utf-8')).get('status') in ('prepared','recovering','rollback_prepared'):
                raise RuntimeError('An unfinished transaction requires inspection before another installation')
        return _install(bundle,game,apply=True,running=running)


def _install(bundle,game,*,apply=False,running=game_running):
    bundle=Path(bundle).resolve()
    if not verify(bundle)['passed']: raise ValueError('Bundle integrity failed')
    game,target=target_for(game)
    source=bundle/'collector'
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('Id')!='LandlordResearch' or manifest.get('AssemblyPath')!='LandlordResearch.dll':
        raise ValueError('Wrong collector manifest')
    original=tree_hashes(target)
    if running(): raise RuntimeError('Close the game before installing')
    if not apply: return {'operation':'install','applied':False,'target':str(target),'existing_files':original}
    backups=game/'SlotWeave/research-backups'
    if backups.resolve()!=backups: raise ValueError('Redirected backup path refused')
    transaction=backups/uuid.uuid4().hex
    transaction.mkdir(parents=True,exist_ok=False)
    stage=transaction/'staged'
    if target.exists(): shutil.copytree(target,stage)
    else: stage.mkdir()
    for name in ('LandlordResearch.dll','manifest.json'): shutil.copy2(source/name,stage/name)
    receipt={'format':1,'game':str(game),'target':str(target),'before':original,
             'installed':tree_hashes(stage),'status':'prepared'}
    write_receipt(transaction,receipt)
    if running() or tree_hashes(target)!=original: raise RuntimeError('Game or plugin changed during preparation')
    target.parent.mkdir(parents=True,exist_ok=True)
    moved=False
    try:
        if target.exists(): target.rename(transaction/'previous'); moved=True
        stage.rename(target)
    except OSError:
        if moved and not target.exists(): (transaction/'previous').rename(target)
        receipt['status']='install_failed'; write_receipt(transaction,receipt)
        raise
    receipt['status']='installed'; write_receipt(transaction,receipt)
    return {'operation':'install','applied':True,'receipt':str(transaction/'receipt.json')}


def rollback(receipt_path,game,*,apply=False,running=game_running):
    if not apply: return _rollback(receipt_path,game,apply=False,running=running)
    with installation_lock(game):
        return _rollback(receipt_path,game,apply=True,running=running)


def _rollback(receipt_path,game,*,apply=False,running=game_running):
    game,target=target_for(game)
    path=Path(receipt_path).resolve(); directory=path.parent
    backup_root=game/'SlotWeave/research-backups'
    if path.name!='receipt.json' or directory.parent!=backup_root or directory.resolve()!=directory:
        raise ValueError('Receipt must be in this game backup directory')
    receipt=json.loads(path.read_text(encoding='utf-8'))
    if (receipt.get('format')!=1 or receipt.get('game')!=str(game) or receipt.get('target')!=str(target)
            or receipt.get('status')!='installed'): raise ValueError('Receipt is not an installed transaction for this game')
    if tree_hashes(target)!=receipt['installed']: raise ValueError('Installed files changed; preserve and inspect before rollback')
    previous=directory/'previous'
    if tree_hashes(previous)!=receipt['before']: raise ValueError('Original backup does not match receipt')
    if running(): raise RuntimeError('Close the game before rollback')
    if not apply: return {'operation':'rollback','applied':False,'target':str(target)}
    archive=directory/'removed-install'
    if archive.exists(): raise ValueError('Rollback archive already exists')
    receipt['status']='rollback_prepared'
    receipt['restore_archive']='removed-install'
    write_receipt(directory,receipt)
    _restore(path,game,running=running)
    return {'operation':'rollback','applied':True,'receipt':str(path)}


def inspect_transaction(receipt_path,game):
    """Classify retained evidence; do not guess when bytes differ."""
    game,target=target_for(game)
    path=Path(receipt_path).resolve(); directory=path.parent
    if path.name!='receipt.json' or directory.parent!=game/'SlotWeave/research-backups':
        raise ValueError('Receipt must be in this game backup directory')
    receipt=json.loads(path.read_text(encoding='utf-8'))
    if (receipt.get('format')!=1 or receipt.get('game')!=str(game)
            or receipt.get('target')!=str(target)
            or 'before' not in receipt
            or not isinstance(receipt.get('installed'),dict)
            or not (receipt.get('before') is None or isinstance(receipt['before'],dict))):
        raise ValueError('Invalid transaction receipt')
    status=receipt.get('status')
    current,previous,staged=(tree_hashes(p) for p in (target,directory/'previous',directory/'staged'))
    phase='conflict'
    if status in ('prepared','install_failed'):
        if staged not in (None,receipt['installed']):
            phase='conflict'
        elif current==receipt['before'] and previous is None:
            phase='not_switched'
        elif receipt['before'] is not None and previous==receipt['before'] and current is None:
            phase='original_archived'
        elif current==receipt['installed'] and previous==receipt['before']:
            phase='replacement_in_place'
    elif status in ('installed','rolled_back','recovered'):
        phase='already_finalized'
    elif status in ('recovering','rollback_prepared'):
        archive_name=receipt.get('restore_archive')
        if archive_name not in ('removed-install','recovery-installed'):
            raise ValueError('Invalid restoration archive')
        archive=tree_hashes(directory/archive_name)
        if staged not in (None,receipt['installed']) or archive not in (None,receipt['installed']):
            phase='conflict'
        elif current==receipt['before'] and previous is None:
            phase='restoration_complete'
        elif current is None and previous==receipt['before']:
            phase='restore_original'
        elif current==receipt['installed'] and previous==receipt['before'] and archive is None:
            phase='restore_pending'
    return {'operation':'inspect','receipt':str(path),'status':status,'phase':phase,
            'recoverable':phase in ('not_switched','original_archived','replacement_in_place',
                                   'restoration_complete','restore_original','restore_pending')}


def recover(receipt_path,game,*,apply=False,running=game_running):
    if not apply: return inspect_transaction(receipt_path,game)
    with installation_lock(game):
        return _restore(receipt_path,game,running=running)


def _restore(receipt_path,game,*,running):
    result=inspect_transaction(receipt_path,game)
    if not result['recoverable']: raise ValueError('Cannot recover automatically: '+result['phase'])
    if running(): raise RuntimeError('Close the game before recovery')
    _,target=target_for(game)
    path=Path(result['receipt']); directory=path.parent
    receipt=json.loads(path.read_text(encoding='utf-8'))
    if receipt['status'] not in ('recovering','rollback_prepared'):
        if (directory/'recovery-installed').exists(): raise ValueError('Unexpected recovery archive')
        receipt['status']='recovering'; receipt['restore_archive']='recovery-installed'
        write_receipt(directory,receipt)
    previous=directory/'previous'; archive=directory/receipt['restore_archive']
    if result['phase'] in ('replacement_in_place','restore_pending'):
        target.rename(archive)
        try:
            if previous.exists(): previous.rename(target)
        except OSError:
            archive.rename(target)
            raise
    elif result['phase'] in ('original_archived','restore_original'):
        if previous.exists(): previous.rename(target)
    if tree_hashes(target)!=receipt['before']:
        raise RuntimeError('Recovery verification failed; retained files require inspection')
    receipt['status']='rolled_back' if receipt['status']=='rollback_prepared' else 'recovered'
    write_receipt(directory,receipt)
    return {'operation':'recover','applied':True,'receipt':str(path),'restored':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['install','rollback','inspect','recover'])
    parser.add_argument('--game',required=True,type=Path)
    parser.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--receipt',type=Path)
    parser.add_argument('--apply',action='store_true',help='Apply the operation; otherwise inspect only')
    args=parser.parse_args()
    if args.operation!='install' and args.receipt is None: parser.error('--receipt required')
    try:
        if args.operation=='install': result=install(args.bundle,args.game,apply=args.apply)
        elif args.operation=='rollback': result=rollback(args.receipt,args.game,apply=args.apply)
        elif args.operation=='inspect': result=inspect_transaction(args.receipt,args.game)
        else: result=recover(args.receipt,args.game,apply=args.apply)
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print(json.dumps({'status':'error','changes_may_have_occurred':args.apply,
                          'error':str(error)})); raise SystemExit(1)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
