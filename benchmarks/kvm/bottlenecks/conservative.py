#!/usr/bin/env python3
"""Export/build combinations excluding measured memo/moving-facing regressions."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

import candidates as c
import supplement_support as support
base=c.base
ROOT=c.ROOT
WORK=base.WORK/'conservative'
RESULTS=c.HERE/'conservative-results'
LOG=[]
sys.path.insert(0,str(c.HERE/'fallback'))
import run_fallback
sys.path.insert(0,str(c.HERE/'priority'))
import run_priority


def states_and_export():
    heap=c.heap_base();state=dict(heap)
    for number,label,name,fn in c.SPECS:
        if name not in ('memo','facing'):fn(state)
    run_fallback.transform(state)
    cached=dict(state);run_priority.transform(cached)
    master={p:c.source(c.MASTER,p) for p in c.FILES}
    outputs={}
    for name,target in (('conservative',state),('conservative-memory',cached)):
        for suffix,before in (('after-heap',heap),('from-master',master)):
            filename=name+'-'+suffix+'.patch'
            text=c.diff(before,target,'Excludes optional 0011 memo and 0013 facing; '+('includes optional +35 KiB priority cache' if name.endswith('memory') else 'no extra priority array'),'0003 ONLY' if suffix=='after-heap' else 'Clean pinned master ONLY')
            path=c.PATCHES/filename;path.write_text(text);support.verify_export(before,target,path)
            outputs[filename]=target
    # The diagnostic is optional and must also compose with both preferred forms.
    for target in (state,cached):
        diagnostic=dict(target);c.diagnostic(diagnostic)
        support.verify_export(target,diagnostic,c.PATCHES/'0017-npc-lag-breakdown.patch')
    support.verify_export(state,cached,c.PATCHES/run_priority.FILENAME)
    return state,cached


def command(args):
    args=list(map(str,args));p=subprocess.run(args,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1800)
    LOG.append('$ '+' '.join(args).replace(str(ROOT),'<repo>')+'\n'+p.stdout.replace(str(ROOT),'<repo>'))
    if p.returncode:print(p.stdout,end='',flush=True);raise RuntimeError('Conservative full build')
    return p.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--export-only',action='store_true');parser.add_argument('--results',type=Path,default=RESULTS)
    args=parser.parse_args();states=states_and_export()
    if args.export_only:print('PASS conservative exports');return
    support.verify_primary();args.results.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    footprints={}
    for name,state in zip(('conservative','conservative-memory'),states):
        for diagnostic in (False,True):
            label=name+('-diagnostic' if diagnostic else '')
            candidate=dict(state)
            if diagnostic:c.diagnostic(candidate)
            print('Full build',label,flush=True)
            footprints[label]=support.build_full(candidate,WORK/label,command)
    inputs=[Path(__file__),c.HERE/'supplement_support.py',c.HERE/'fallback/run_fallback.py',c.HERE/'priority/run_priority.py']+sorted(c.PATCHES.glob('conservative*.patch'))
    metadata=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),base_master=c.MASTER,footprints=footprints,
        input_sha256={str(p.relative_to(ROOT)):base.sha(p.read_bytes()) for p in inputs},
        primary_environment_sha256=base.sha((c.HERE/'results/environment.json').read_bytes()),
        pspkvm_tested_here=False,whole_combination_timed=False,excluded_optional_patches=['0011','0013'],diagnostic_excluded_from_runtime_bundles=True)
    (args.results/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n');(args.results/'commands.log').write_text('\n'.join(LOG))
    (args.results/'validation.txt').write_text('PASS: four conservative full-game builds/preverification including diagnostic composition; patch apply/reverse and exact prototype checks. No fresh whole-combination timing claimed.\n')
    print('PASS conservative combinations',flush=True)


if __name__=='__main__':main()
