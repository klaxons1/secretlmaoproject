"""Shared integrity/build helpers for the separately timed supplements."""
import os
from pathlib import Path
import shutil
import subprocess

import candidates as c
import run_bottlenecks as primary
base=c.base
ROOT=c.ROOT


def verify_primary():
    import json
    meta=json.loads((primary.RESULTS/'environment.json').read_text())
    if meta['base_master']!=c.MASTER or meta['kvm_sha256']!=base.KVM_SHA256 or base.sha(base.kvm_binary().read_bytes())!=base.KVM_SHA256:
        raise ValueError('Primary tool/source pin changed')
    for field,directory in (('input_sha256',ROOT),('resources_sha256',ROOT/'res'),('generated_java_sha256',primary.WORK),('headless_class_sha256',primary.WORK/'verified')):
        for name,expected in meta[field].items():
            path=directory/name
            if not path.is_file() or base.sha(path.read_bytes())!=expected:raise ValueError('Frozen primary mismatch: '+str(path))
    for directory in ('src','common/src'):
        for path in sorted((ROOT/directory).glob('*.java')):
            if path.read_text()!=c.source(c.MASTER,str(path.relative_to(ROOT))):raise ValueError('Keep production source at pinned master: '+str(path))
    return meta


def build_full(state,directory,command):
    """Same Java 1.3/45.3 + CLDC StackMap settings as the main build."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    files=[]
    for path in sorted((ROOT/'src').glob('*.java'))+sorted((ROOT/'common/src').glob('*.java')):
        relative=str(path.relative_to(ROOT))
        if relative in state:
            target=directory/'source'/path.name;target.parent.mkdir(exist_ok=True);target.write_text(state[relative]);files.append(target)
        else:files.append(path)
    raw=directory/'raw'
    if raw.exists():shutil.rmtree(raw)
    raw.mkdir()
    libs=[base.WORK/'suite/uei'/name for name in ('cldc11.jar','midp21.jar','jsr135.jar','jsr184.jar','nokiaui.jar')]
    command([base.jdk('javac'),'-source','1.3','-target','1.3','-Xlint:-options','-bootclasspath',libs[0],'-classpath',os.pathsep.join(map(str,libs[1:])),'-d',raw,*files])
    verified=directory/'verified'
    if verified.exists():shutil.rmtree(verified)
    args=[base.jdk('java'),'-jar',base.WORK/'suite/libs/proguard.jar','-injars',raw,'-outjars',verified]
    for lib in libs:args+=['-libraryjars',lib]
    command(args+['-dontshrink','-dontoptimize','-dontobfuscate','-microedition','-target','1.1'])
    result={}
    for name in ('Game','NPC'):
        data=(verified/(name+'.class')).read_bytes()
        if data[4:8]!=b'\x00\x03\x00\x2d' or b'StackMap' not in data:raise ValueError('CLDC preverification: '+name)
        result[name+'_bytes']=len(data);result[name+'_sha256']=base.sha(data)
    result['source_sha256']={path:base.sha(text.encode()) for path,text in state.items()}
    return result


def verify_export(before,after,patch):
    """Apply/reverse without checking out or staging real production sources."""
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(directory)/'index'))
        def git(*args):return subprocess.check_output(['git',*map(str,args)],cwd=ROOT,env=env,stderr=subprocess.STDOUT)
        git('read-tree',c.MASTER)
        for path,text in before.items():
            blob=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=ROOT,env=env,input=text.encode()).decode().strip()
            git('update-index','--cacheinfo','100644,'+blob+','+path)
        git('apply','--cached','--check','--whitespace=error',patch);git('apply','--cached',patch)
        for path in c.FILES:
            if git('show',':'+path).decode()!=after[path]:raise ValueError('Export prototype mismatch: '+str(patch))
        git('apply','--cached','--reverse',patch)
        for path in c.FILES:
            if git('show',':'+path).decode()!=before[path]:raise ValueError('Export reversal mismatch: '+str(patch))
