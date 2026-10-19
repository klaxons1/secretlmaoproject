#!/usr/bin/env python3
"""Supplement: remove duplicate failed fallback when inmate==false.

Separate source/data series; does not change any primary benchmark input file.
Requires a completed primary build in ../.work/bottlenecks (run it first).
"""
import argparse
import csv
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import candidates as c
import run_bottlenecks as primary
import supplement_support as support
base=c.base
ROOT=c.ROOT
WORK=base.WORK/'fallback'
RESULTS=HERE/'results'
FILENAME='0018-avoid-identical-failed-fallback.patch'
LOG=[]
RAW_FIELDS=primary.RAW_FIELDS
NAMES=('heap-original','heap-once','core-original','core-once')


def transform(state):
    text=state['src/NPC.java']
    body=base.method(text,'void tickAI(')
    pattern=r'\|\| map\.pathfind\(([^\n]+), false, path\)\)'
    updated,count=re.subn(pattern,r'|| (inmate && map.pathfind(\1, false, path)))',body)
    if count!=2:raise ValueError('Expected exactly two roam/work fallback call sites')
    state['src/NPC.java']=c.once(text,body,updated)


def expression(state):
    body=base.method(state['src/NPC.java'],'void tickAI(')
    match=re.search(r'map\.pathfind\(x / TILE_SIZE,[^\n]+inmate, path\)\s*// fallback\s*\|\|[^\n]+',body)
    if not match:raise ValueError('Missing actual NPC fallback expression')
    text=match.group(0)
    if not text.endswith(') {'):raise ValueError('Unexpected enclosing if')
    return text[:-3]


def command(args):
    args=list(map(str,args));p=subprocess.run(args,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1800)
    LOG.append('$ '+' '.join(args).replace(str(ROOT),'<repo>')+'\n'+p.stdout.replace(str(ROOT),'<repo>'))
    if p.returncode:print(p.stdout,end='',flush=True);raise RuntimeError('Command failed ('+str(p.returncode)+'): '+args[0])
    return p.stdout


def export():
    baseline=c.heap_base();after=dict(baseline);transform(after)
    text=c.diff(baseline,after,'Skip an IDENTICAL repeated failed pathfind for non-inmates; true staff-door fallback retained','0003; composable after 0004-0017; direct caller optimization, not a change to pathfinding')
    (c.PATCHES/FILENAME).write_text(text)
    (c.PATCHES/'standalone'/FILENAME).write_text(text)
    allstate=c.variants()['all'];allafter=dict(allstate);transform(allafter)
    (c.PATCHES/'all-plus-fallback-after-heap.patch').write_text(c.diff(baseline,allafter,'Combined 0004-0016 plus 0018; NO diagnostic','0003 ONLY; alternative to the series'))
    original={p:c.source(c.MASTER,p) for p in c.FILES}
    (c.PATCHES/'all-plus-fallback-from-master.patch').write_text(c.diff(original,allafter,'Combined heap, 0004-0016 and 0018; NO diagnostic','Clean pinned master ONLY'))
    (c.PATCHES/'series-plus-fallback.txt').write_text((c.PATCHES/'series.txt').read_text()+FILENAME+'\n')
    with tempfile.TemporaryDirectory() as directory:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(directory)/'index'))
        def git(*args):return subprocess.check_output(['git',*map(str,args)],cwd=ROOT,env=env,stderr=subprocess.STDOUT)
        for combined in ('all-after-heap.patch',None):
            git('read-tree',c.MASTER);git('apply','--cached',ROOT/'patches/0003-use-stable-heap-pathfinding.patch')
            if combined:git('apply','--cached',c.PATCHES/combined)
            git('apply','--cached','--check','--whitespace=error',c.PATCHES/FILENAME)
            git('apply','--cached',c.PATCHES/FILENAME)
            expected=allafter if combined else after
            for path in c.FILES:
                if git('show',':'+path).decode()!=expected[path]:raise ValueError('Fallback patch composition')
            git('apply','--cached','--reverse',c.PATCHES/FILENAME)
        for filename,heap in (('all-plus-fallback-after-heap.patch',True),('all-plus-fallback-from-master.patch',False)):
            git('read-tree',c.MASTER)
            if heap:git('apply','--cached',ROOT/'patches/0003-use-stable-heap-pathfinding.patch')
            git('apply','--cached','--check','--whitespace=error',c.PATCHES/filename)
            git('apply','--cached',c.PATCHES/filename)
            for path in c.FILES:
                if git('show',':'+path).decode()!=allafter[path]:raise ValueError('Fallback combined source')
    return baseline,after,allafter


def build(states):
    original,changed,combined=states
    verified=primary.WORK/'verified'
    if not (verified/'PerfGame.class').is_file():raise RuntimeError('Build the primary suite first')
    generated=WORK/'source';generated.mkdir(parents=True,exist_ok=True)
    for name,state in (('OriginalRequest',original),('OnceRequest',changed)):
        body=expression(state)
        direct='final class '+name+' extends RequestBase { boolean request(){ return '+body+'; } }\n'
        (generated/(name+'.java')).write_text(direct)
        counted=direct.replace('class '+name,'class Counted'+name,1).replace('map.pathfind(','counted(')
        (generated/('Counted'+name+'.java')).write_text(counted)
    api=base.WORK/'cldc/j2me_cldc/bin/common/api/classes'
    raw=WORK/'raw'
    if raw.exists():shutil.rmtree(raw)
    raw.mkdir()
    command([base.jdk('javac'),'-source','1.3','-target','1.3','-Xlint:-options','-bootclasspath',api,'-classpath',verified,'-d',raw,HERE/'FallbackBench.java',*sorted(generated.glob('*.java'))])
    out=WORK/'verified'
    if out.exists():shutil.rmtree(out)
    command([base.jdk('java'),'-jar',base.WORK/'suite/libs/proguard.jar','-injars',raw,'-outjars',out,'-libraryjars',api,'-libraryjars',verified,'-dontskipnonpubliclibraryclasses','-dontskipnonpubliclibraryclassmembers','-dontshrink','-dontoptimize','-dontobfuscate','-microedition','-target','1.1'])
    shutil.copytree(verified,out,dirs_exist_ok=True)
    libs=[base.WORK/'suite/uei'/name for name in ('cldc11.jar','midp21.jar','jsr135.jar','jsr184.jar','nokiaui.jar')]
    production=sorted((ROOT/'src').glob('*.java'))+sorted((ROOT/'common/src').glob('*.java'))
    footprints={}
    for label,state in (('heap-fallback',changed),('all-fallback',combined)):
        directory=WORK/label;directory.mkdir(exist_ok=True)
        files=[]
        for path in production:
            relative=str(path.relative_to(ROOT))
            if relative in state:
                target=directory/'source'/path.name;target.parent.mkdir(exist_ok=True);target.write_text(state[relative]);files.append(target)
            else:files.append(path)
        output=directory/'raw'
        if output.exists():shutil.rmtree(output)
        output.mkdir()
        command([base.jdk('javac'),'-source','1.3','-target','1.3','-Xlint:-options','-bootclasspath',libs[0],'-classpath',os.pathsep.join(map(str,libs[1:])),'-d',output,*files])
        pre=directory/'verified'
        if pre.exists():shutil.rmtree(pre)
        args=[base.jdk('java'),'-jar',base.WORK/'suite/libs/proguard.jar','-injars',output,'-outjars',pre]
        for lib in libs:args+=['-libraryjars',lib]
        command(args+['-dontshrink','-dontoptimize','-dontobfuscate','-microedition','-target','1.1'])
        data=(pre/'NPC.class').read_bytes()
        if data[4:8]!=b'\x00\x03\x00\x2d' or b'StackMap' not in data:raise ValueError('CLDC verification')
        footprints[label]={'NPC_bytes':len(data),'NPC_sha256':base.sha(data)}
    return footprints


def validate(rows,samples):
    if not rows:raise ValueError('Empty supplement timing data')
    groups={}
    for r in rows:
        if set(r)!=set(RAW_FIELDS) or r['engine']!='original-kvm-1.1' or r['family']!='fallback' or r['variant'] not in NAMES:raise ValueError('Supplement raw schema')
        if len(r['scenario'].split(':'))!=2 or r['scenario'].split(':')[0] not in base.MAPS:raise ValueError('Supplement scenario')
        if r['scenario'].split(':')[1] not in ('guard-failure','guard-success','inmate-policy'):raise ValueError('Supplement distribution')
        row=dict(r)
        for field in RAW_FIELDS[4:]:row[field]=int(row[field])
        if min(row['iterations'],row['operations'],row['elapsed_ms'])<=0 or row['operations']%row['iterations']:raise ValueError('Supplement normalization')
        groups.setdefault(row['scenario'],[]).append(row)
    for scenario,group in groups.items():
        if len(group)!=samples*len(NAMES) or len({(r['sample'],r['variant']) for r in group})!=len(group):raise ValueError('Supplement missing/duplicate')
        if len({r['operations']//r['iterations'] for r in group})!=1:raise ValueError('Supplement work units differ')
        if len({r['checksum'] for r in group})!=1:raise ValueError('Supplement checksum')
        for sample in range(samples):
            trial=sorted([r for r in group if r['sample']==sample],key=lambda r:r['order'])
            if [r['order'] for r in trial]!=list(range(4)) or [r['variant'] for r in trial]!=[NAMES[i] for i in primary.order_for(sample,4)]:raise ValueError('Supplement rotation')
    return groups


def analyze(rows,destination,samples):
    import statistics
    groups=validate(rows,samples);summary=[];pairs=[];lines=['# Duplicate-fallback paired calculations','', 'All units are complete NPC requests; one request can call pathfind twice.','']
    for scenario,group in sorted(groups.items()):
        by={(r['variant'],r['sample']):r for r in group}
        for reference,candidate in (('heap-original','heap-once'),('core-original','core-once'),('heap-original','core-once')):
            a=[];b=[]
            for sample in range(samples):
                old,new=by[reference,sample],by[candidate,sample]
                a.append(old['elapsed_ms']*1000.0/old['operations']);b.append(new['elapsed_ms']*1000.0/new['operations'])
                pairs.append(dict(scenario=scenario,reference=reference,candidate=candidate,sample=sample,reference_us=a[-1],candidate_us=b[-1],speedup=a[-1]/b[-1]))
            ratios=[x/y for x,y in zip(a,b)];speed=statistics.median(ratios)
            summary.append(dict(family='fallback',scenario=scenario,reference=reference,candidate=candidate,samples=samples,reference_us_median=statistics.median(a),candidate_us_median=statistics.median(b),speedup_median=speed,time_reduction_percent=100*(1-1/speed),speedup_min=min(ratios),speedup_max=max(ratios)))
            lines+=['## '+scenario+' '+reference+' -> '+candidate,'']
            lines += ['sample %d: %.9f / %.9f = %.9f'%(i,x,y,x/y) for i,(x,y) in enumerate(zip(a,b))]
            lines+=['median %.9f; reduction %.9f%%'%(speed,100*(1-1/speed)),'']
    destination.mkdir(parents=True,exist_ok=True)
    primary.write_csv(destination/'summary.csv',primary.SUMMARY_FIELDS,summary)
    primary.write_csv(destination/'paired.csv',('scenario','reference','candidate','sample','reference_us','candidate_us','speedup'),pairs)
    (destination/'calculations.md').write_text('\n'.join(lines)+'\n')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=RESULTS)
    parser.add_argument('--samples',type=int,default=12)
    parser.add_argument('--min-ms',type=int,default=150)
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--export-only',action='store_true')
    parser.add_argument('--analyze',type=Path)
    args=parser.parse_args()
    if args.samples<2 or args.min_ms<20:parser.error('samples >= 2 and min-ms >= 20')
    forbidden=(primary.RESULTS,base.HERE/'results',base.HERE/'experiments/results')
    if args.results.resolve() in [p.resolve() for p in forbidden]:raise ValueError('Do not overwrite other published result series')
    args.results.mkdir(parents=True,exist_ok=True)
    if args.analyze:
        with args.analyze.open() as stream:rows=list(csv.DictReader(stream))
        analyze(rows,args.results,args.samples);return
    if args.export_only:export();print('PASS supplement exports');return
    support.verify_primary()
    WORK.mkdir(parents=True,exist_ok=True)
    states=export();footprints=build(states)
    outputs=[]
    for engine,commandline in (('desktop Java',[base.jdk('java'),'-Xmx512m','-cp',WORK/'verified']),('original KVM 1.1',base.kvm_command()[:-1]+[WORK/'verified'])):
        out=command(commandline+['FallbackBench','check'])
        if 'CHECKS,PASS' not in out:raise ValueError('Missing fallback sentinel')
        print(engine+'\n'+out,end='',flush=True);outputs.append(engine+'\n'+out)
    (args.results/'validation.txt').write_text('\n'.join(outputs))
    fixtures=command(base.kvm_command()[:-1]+[WORK/'verified','FallbackBench','fixtures'])
    fixture_rows=[line.split(',')[1:] for line in fixtures.splitlines() if line.startswith('QUERY,')]
    if len(fixture_rows)!=18*8:raise ValueError('Fallback fixture completeness')
    selection_rows=[line.split(',')[1:] for line in fixtures.splitlines() if line.startswith('SELECT,')]
    if len(selection_rows)!=18:raise ValueError('Fallback selection completeness')
    primary.write_csv(args.results/'fixture-selection.csv',('scenario','walkable_selected','blocked_target_selected'),[dict(zip(('scenario','walkable_selected','blocked_target_selected'),r)) for r in selection_rows])
    primary.write_csv(args.results/'query-fixtures.csv',('scenario','index','start_x','start_y','direction','target_x','target_y','inmate','blocked_target'),[dict(zip(('scenario','index','start_x','start_y','direction','target_x','target_y','inmate','blocked_target'),r)) for r in fixture_rows])
    if not args.check_only:
        rows=[];counts=[]
        for name in base.MAPS:
            for distribution in ('guard-failure','guard-success','inmate-policy'):
                scenario=name+':'+distribution;print('Benchmark fallback',scenario,flush=True)
                out=command(base.kvm_command()[:-1]+[WORK/'verified','FallbackBench','time',scenario,args.samples,args.min_ms])
                for line in out.splitlines():
                    fields=line.split(',')
                    if fields[0]=='RESULT':
                        if len(fields)!=len(RAW_FIELDS):raise ValueError('Fallback CSV schema')
                        rows.append(dict(zip(RAW_FIELDS,['original-kvm-1.1']+fields[1:])))
                    elif fields[0]=='CALLS':
                        if len(fields)!=6:raise ValueError('Fallback count schema')
                        counts.append(dict(zip(('scenario','variant','requests','path_calls','checksum'),fields[1:])))
                primary.write_csv(args.results/'raw.csv',RAW_FIELDS,rows)
                primary.write_csv(args.results/'call-counts.csv',('scenario','variant','requests','path_calls','checksum'),counts)
                (args.results/'commands.log').write_text('\n'.join(LOG))
        if len(rows)!=18*4*args.samples or len(counts)!=18*4:raise ValueError('Fallback matrix incomplete')
        analyze(rows,args.results,args.samples)
    inputs=[Path(__file__),HERE.parent/'supplement_support.py',HERE/'FallbackBench.java',c.PATCHES/FILENAME,c.PATCHES/'all-plus-fallback-after-heap.patch',c.PATCHES/'all-plus-fallback-from-master.patch']
    metadata=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),base_master=c.MASTER,kvm_sha256=base.sha(base.kvm_binary().read_bytes()),samples=args.samples,target_ms=args.min_ms,
        primary_environment_sha256=base.sha((primary.RESULTS/'environment.json').read_bytes()),footprints=footprints,
        headless_class_sha256={p.name:base.sha(p.read_bytes()) for p in sorted((WORK/'verified').glob('*.class'))},
        input_sha256={str(p.relative_to(ROOT)):base.sha(p.read_bytes()) for p in inputs},source_sha256={str(p.relative_to(ROOT)):base.sha(p.read_bytes()) for p in sorted((WORK/'source').glob('*.java'))},
        pspkvm_tested_here=False,primary_raw_preserved=True,
        limitations=['Separate series, not pooled with primary intervals','Buffer 400 shorts, matching NPC.path; false can mean unreachable or short buffer','guard-failure fills missing native false-returning walkable queries with explicitly labeled solid-target stress controls; see fixture-selection.csv; NOT their frequency in play','inmate-policy retains different-door-policy fallback','Request bodies are extracted from actual NPC source; pathfind/geometry from already validated primary classes','Counter wrappers are separate and are never timed','Removing a duplicate NO PATH log changes diagnostic output count, not game decisions'])
    (args.results/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (args.results/'commands.log').write_text('\n'.join(LOG))
    print('PASS: fallback supplement',flush=True)


if __name__=='__main__':main()
