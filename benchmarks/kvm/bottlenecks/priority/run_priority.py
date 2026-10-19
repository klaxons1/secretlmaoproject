#!/usr/bin/env python3
"""Separate memory-for-CPU experiment: cached int frontier priorities.

Requires 0007 decrease-key. Primary benchmark inputs/results are never edited.
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
WORK=base.WORK/'priority'
RESULTS=HERE/'results'
FILENAME='0019-cache-heap-priorities.patch'
LOG=[]
NAMES=('heap','decrease','decrease-key','core','core-key')


def transform(state):
    text=state['src/Game.java']
    if 'void openImprove(int n)' not in text:raise ValueError('Priority cache requires 0007; openImprove must update the cache too')
    text=c.once(text,'\tshort[] nodeG, nodeH;','\tshort[] nodeG, nodeH;\n\tprivate int[] openHeapPriority;')
    text=c.once(text,'\t\tnodeH = new short[size];','\t\tnodeH = new short[size];\n\t\topenHeapPriority = new int[size];')
    for signature in ('void openAdd(','void openRemove(','void openImprove('):
        def edit(body):
            body=c.once(body,'\n\t\tshort[] heap = openHeap;', '\n\t\tint[] priority = openHeapPriority;\n\t\tshort[] heap = openHeap;')
            body=c.once(body,'\t\tshort[] g = nodeG, h = nodeH;\n','')
            body,count=re.subn(r'g\[(\w+)\] \+ h\[\1\]',r'priority[\1]',body)
            if count<2:raise ValueError('Unknown heap comparison layout')
            if signature!='void openRemove(':
                body=c.once(body,'int f = priority[n];','int f = priority[n] = nodeG[n] + nodeH[n];')
            return body
        text=c.change_method(text,signature,edit)
    state['src/Game.java']=text


def command(args):
    args=list(map(str,args));p=subprocess.run(args,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1800)
    LOG.append('$ '+' '.join(args).replace(str(ROOT),'<repo>')+'\n'+p.stdout.replace(str(ROOT),'<repo>'))
    if p.returncode:print(p.stdout,end='',flush=True);raise RuntimeError('Command failed: '+args[0])
    return p.stdout


def states_and_export():
    heap=c.heap_base();decreased=dict(heap);c.decrease(decreased)
    cached=dict(decreased);transform(cached)
    core=c.variants()['core'];corecached=dict(core);transform(corecached)
    text=c.diff(decreased,cached,'Cache signed-int F priorities; +4*mapCells bytes; requires decrease-key update hook','0003 AND 0007; or core/all containing 0007. Do not use with a stale openImprove implementation')
    (c.PATCHES/FILENAME).write_text(text)
    (c.PATCHES/'standalone'/FILENAME).write_text(text)
    full=c.variants()['all']
    sys.path.insert(0,str(HERE.parent/'fallback'))
    import run_fallback
    run_fallback.transform(full);fullcached=dict(full);transform(fullcached)
    (c.PATCHES/'all-memory-after-heap.patch').write_text(c.diff(heap,fullcached,'All CPU/render/release patches plus 0018/0019, NO diagnostic; additional priority-array memory','0003 ONLY; alternative to all other combined files'))
    master={p:c.source(c.MASTER,p) for p in c.FILES}
    (c.PATCHES/'all-memory-from-master.patch').write_text(c.diff(master,fullcached,'Heap plus all CPU/render/release patches including 0018/0019, NO diagnostic','Clean pinned master ONLY; +35 KiB beyond the normal heap for cached priorities'))
    with tempfile.TemporaryDirectory() as directory:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(directory)/'index'))
        def git(*args):return subprocess.check_output(['git',*map(str,args)],cwd=ROOT,env=env,stderr=subprocess.STDOUT)
        for prefix,expected in ((None,cached),('all-plus-fallback-after-heap.patch',fullcached)):
            git('read-tree',c.MASTER);git('apply','--cached',ROOT/'patches/0003-use-stable-heap-pathfinding.patch')
            if prefix:git('apply','--cached',c.PATCHES/prefix)
            else:git('apply','--cached',c.PATCHES/'standalone/0007-heap-decrease-key.patch')
            git('apply','--cached','--check','--whitespace=error',c.PATCHES/FILENAME);git('apply','--cached',c.PATCHES/FILENAME)
            for path in c.FILES:
                if git('show',':'+path).decode()!=expected[path]:raise ValueError('Priority patch composition')
            git('apply','--cached','--reverse',c.PATCHES/FILENAME)
        for filename,heapfirst in (('all-memory-after-heap.patch',True),('all-memory-from-master.patch',False)):
            git('read-tree',c.MASTER)
            if heapfirst:git('apply','--cached',ROOT/'patches/0003-use-stable-heap-pathfinding.patch')
            git('apply','--cached','--check','--whitespace=error',c.PATCHES/filename);git('apply','--cached',c.PATCHES/filename)
            for path in c.FILES:
                if git('show',':'+path).decode()!=fullcached[path]:raise ValueError('Memory combined source')
    return {'decrease-key':cached,'core-key':corecached},fullcached


def build(states,full):
    source=WORK/'source';source.mkdir(parents=True,exist_ok=True)
    for name,state in states.items():
        region=state['src/Game.java'].split('\t// region Pathfinding\n',1)[1].split('\t// endregion Pathfinding',1)[0]
        # Keep the new private priority array, while inheriting the old fields.
        region=re.sub(r'^\t(?:short|byte|int)(?:\[\])? [\w, ]+;\n','',region,flags=re.M)
        helpers='\n'.join(base.method(state['src/Game.java'],sig) for sig in ('int getObjectIdxAt(','int findObject(','int getSeatIndex(','boolean isInZone(int x,','int findZone('))
        if 'void ensureZoneIndex(' in state['src/Game.java']:helpers+='\n'+base.method(state['src/Game.java'],'void ensureZoneIndex(')
        classname='Priority_'+name.replace('-','_')
        (source/(classname+'.java')).write_text('final class '+classname+' extends PerfGame implements PrioritySource {\n'+region+'\n'+helpers+'\npublic int priorityAt(int n){return openHeapPriority[n];}\n}\n')
    factory='''interface PrioritySource { int priorityAt(int n); }
final class PriorityFactories {
static final String[] PATH_NAMES={"heap","decrease","decrease-key","core","core-key"};
static PerfGame game(String name){
if(name.equals("decrease-key"))return new Priority_decrease_key();
if(name.equals("core-key"))return new Priority_core_key();
return Factories.game(name); }
static Actor actor(String name){return Factories.actor(name.endsWith("-key")?name.substring(0,name.length()-4):name);}
}'''
    (source/'PriorityFactories.java').write_text(factory)
    checks=(HERE.parent/'src/PerfChecks.java').read_text().replace('public final class PerfChecks','public final class PriorityChecks').replace('Factories.','PriorityFactories.')
    checks=checks.replace('b=PriorityFactories.game("decrease");','b=PriorityFactories.game("core-key");')
    checks=checks.replace('if(!present[i])continue;','if(!present[i])continue;\n            if(b instanceof PrioritySource)require(((PrioritySource)b).priorityAt(i)==b.nodeG[i]+b.nodeH[i],"Cached active priority");')
    checks=checks.replace('queues();paths();helpers();movement();visions();','queues();paths();helpers();movement();visions();PriorityExtra.checkAnyKeys();')
    checks=checks.replace('six-way-exact-paths','five-way-exact-paths')
    (source/'PriorityChecks.java').write_text(checks)
    raw=WORK/'raw'
    if raw.exists():shutil.rmtree(raw)
    raw.mkdir()
    verified=primary.WORK/'verified';api=base.WORK/'cldc/j2me_cldc/bin/common/api/classes'
    command([base.jdk('javac'),'-source','1.3','-target','1.3','-Xlint:-options','-bootclasspath',api,'-classpath',verified,'-d',raw,HERE/'PriorityBench.java',*sorted(source.glob('*.java'))])
    out=WORK/'verified'
    if out.exists():shutil.rmtree(out)
    command([base.jdk('java'),'-jar',base.WORK/'suite/libs/proguard.jar','-injars',raw,'-outjars',out,'-libraryjars',api,'-libraryjars',verified,'-dontskipnonpubliclibraryclasses','-dontskipnonpubliclibraryclassmembers','-dontshrink','-dontoptimize','-dontobfuscate','-microedition','-target','1.1'])
    shutil.copytree(verified,out,dirs_exist_ok=True)
    libs=[base.WORK/'suite/uei'/name for name in ('cldc11.jar','midp21.jar','jsr135.jar','jsr184.jar','nokiaui.jar')]
    production=sorted((ROOT/'src').glob('*.java'))+sorted((ROOT/'common/src').glob('*.java'))
    footprints={}
    for label,state in [*states.items(),('all-memory',full)]:
        directory=WORK/label;directory.mkdir(exist_ok=True);files=[]
        for path in production:
            relative=str(path.relative_to(ROOT))
            if relative in state:
                target=directory/'source'/path.name;target.parent.mkdir(exist_ok=True);target.write_text(state[relative]);files.append(target)
            else:files.append(path)
        output=directory/'raw'
        if output.exists():shutil.rmtree(output)
        output.mkdir()
        command([base.jdk('javac'),'-source','1.3','-target','1.3','-Xlint:-options','-bootclasspath',libs[0],'-classpath',os.pathsep.join(map(str,libs[1:])),'-d',output,*files])
        dest=directory/'verified'
        if dest.exists():shutil.rmtree(dest)
        args=[base.jdk('java'),'-jar',base.WORK/'suite/libs/proguard.jar','-injars',output,'-outjars',dest]
        for lib in libs:args+=['-libraryjars',lib]
        command(args+['-dontshrink','-dontoptimize','-dontobfuscate','-microedition','-target','1.1'])
        data=(dest/'Game.class').read_bytes()
        if data[4:8]!=b'\x00\x03\x00\x2d' or b'StackMap' not in data:raise ValueError('Priority CLDC verification')
        footprints[label]={'Game_bytes':len(data),'Game_sha256':base.sha(data)}
    return footprints


def validate(rows,samples):
    if not rows:raise ValueError('Empty supplement timing data')
    groups={}
    for r in rows:
        if set(r)!=set(primary.RAW_FIELDS) or r['engine']!='original-kvm-1.1' or r['family']!='priority' or r['variant'] not in NAMES:raise ValueError('Priority raw schema')
        if len(r['scenario'].split(':'))!=2 or r['scenario'].split(':')[0] not in base.MAPS:raise ValueError('Supplement scenario')
        if r['scenario'].split(':')[1] not in ('npc','spread','local'):raise ValueError('Supplement distribution')
        row=dict(r)
        for field in primary.RAW_FIELDS[4:]:row[field]=int(row[field])
        if min(row['iterations'],row['operations'],row['elapsed_ms'])<=0 or row['operations']%row['iterations']:raise ValueError('Priority normalization')
        groups.setdefault(row['scenario'],[]).append(row)
    for scenario,group in groups.items():
        if len(group)!=samples*len(NAMES) or len({(r['sample'],r['variant']) for r in group})!=len(group):raise ValueError('Priority missing/duplicate')
        if len({r['operations']//r['iterations'] for r in group})!=1:raise ValueError('Supplement work units differ')
        if len({r['checksum'] for r in group})!=1:raise ValueError('Priority checksum')
        for sample in range(samples):
            trial=sorted([r for r in group if r['sample']==sample],key=lambda r:r['order'])
            if [r['order'] for r in trial]!=list(range(5)) or [r['variant'] for r in trial]!=[NAMES[i] for i in primary.order_for(sample,5)]:raise ValueError('Priority rotation')
    return groups


def analyze(rows,destination,samples):
    import statistics
    groups=validate(rows,samples);summary=[];pairs=[];lines=['# Cached-priority paired calculations','']
    for scenario,group in sorted(groups.items()):
        by={(r['variant'],r['sample']):r for r in group}
        for reference,candidate in (('decrease','decrease-key'),('core','core-key'),('heap','core-key')):
            a=[];b=[]
            for sample in range(samples):
                old,new=by[reference,sample],by[candidate,sample]
                a.append(old['elapsed_ms']*1000.0/old['operations']);b.append(new['elapsed_ms']*1000.0/new['operations'])
                pairs.append(dict(scenario=scenario,reference=reference,candidate=candidate,sample=sample,reference_us=a[-1],candidate_us=b[-1],speedup=a[-1]/b[-1]))
            ratios=[x/y for x,y in zip(a,b)];speed=statistics.median(ratios)
            summary.append(dict(family='priority',scenario=scenario,reference=reference,candidate=candidate,samples=samples,reference_us_median=statistics.median(a),candidate_us_median=statistics.median(b),speedup_median=speed,time_reduction_percent=100*(1-1/speed),speedup_min=min(ratios),speedup_max=max(ratios)))
            lines+=['## '+scenario+' '+reference+' -> '+candidate,'']+['sample %d: %.9f / %.9f = %.9f'%(i,x,y,x/y) for i,(x,y) in enumerate(zip(a,b))]+['median %.9f; reduction %.9f%%'%(speed,100*(1-1/speed)),'']
    destination.mkdir(parents=True,exist_ok=True)
    primary.write_csv(destination/'summary.csv',primary.SUMMARY_FIELDS,summary)
    primary.write_csv(destination/'paired.csv',('scenario','reference','candidate','sample','reference_us','candidate_us','speedup'),pairs)
    (destination/'calculations.md').write_text('\n'.join(lines)+'\n');return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=RESULTS)
    parser.add_argument('--samples',type=int,default=10)
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
    if args.export_only:states_and_export();print('PASS supplement exports');return
    support.verify_primary()
    WORK.mkdir(parents=True,exist_ok=True)
    states,combined=states_and_export();footprints=build(states,combined);outputs=[]
    for engine,cmd in (('desktop Java',[base.jdk('java'),'-Xmx512m','-cp',WORK/'verified']),('original KVM 1.1',base.kvm_command()[:-1]+[WORK/'verified'])):
        out=command(cmd+['PriorityChecks'])
        if 'CHECKS,PASS' not in out:raise ValueError('Missing priority sentinel')
        print(engine+'\n'+out,end='',flush=True);outputs.append(engine+'\n'+out)
    (args.results/'validation.txt').write_text('\n'.join(outputs))
    if not args.check_only:
        rows=[]
        for name in base.MAPS:
            for distribution in ('npc','spread','local'):
                scenario=name+':'+distribution;print('Benchmark priority',scenario,flush=True)
                out=command(base.kvm_command()[:-1]+[WORK/'verified','PriorityBench',scenario,args.samples,args.min_ms])
                for line in out.splitlines():
                    fields=line.split(',')
                    if fields[0]=='RESULT':
                        if len(fields)!=len(primary.RAW_FIELDS):raise ValueError('Priority CSV schema')
                        rows.append(dict(zip(primary.RAW_FIELDS,['original-kvm-1.1']+fields[1:])))
                primary.write_csv(args.results/'raw.csv',primary.RAW_FIELDS,rows);(args.results/'commands.log').write_text('\n'.join(LOG))
        if len(rows)!=18*5*args.samples:raise ValueError('Priority matrix incomplete')
        analyze(rows,args.results,args.samples)
    inputs=[Path(__file__),HERE.parent/'supplement_support.py',HERE/'PriorityBench.java',c.PATCHES/FILENAME,c.PATCHES/'all-memory-after-heap.patch',c.PATCHES/'all-memory-from-master.patch']
    metadata=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),base_master=c.MASTER,kvm_sha256=base.sha(base.kvm_binary().read_bytes()),samples=args.samples,target_ms=args.min_ms,kvm_heap_bytes=2*1024*1024,
        primary_environment_sha256=base.sha((primary.RESULTS/'environment.json').read_bytes()),footprints=footprints,
        headless_class_sha256={p.name:base.sha(p.read_bytes()) for p in sorted((WORK/'verified').glob('*.class'))},
        input_sha256={str(p.relative_to(ROOT)):base.sha(p.read_bytes()) for p in inputs},source_sha256={str(p.relative_to(ROOT)):base.sha(p.read_bytes()) for p in sorted((WORK/'source').glob('*.java'))},
        priority_payload_bytes=4*96*93,pspkvm_tested_here=False,primary_raw_preserved=True,
        limitations=['Separate series; do not multiply medians from different datasets','heap is original 0003; decrease is 0003+0007; *-key adds only F-cache to that baseline','int rather than short is required because signed-short G+H can exceed short range','Cache initialized on enqueue/improve, stale entries outside frontier are never read','Extra 35712 payload bytes on the shipped 8928-cell maps, beyond heap memory','Not a whole-game profile or physical PSPKVM test'])
    (args.results/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n');(args.results/'commands.log').write_text('\n'.join(LOG))
    print('PASS: priority supplement',flush=True)


if __name__=='__main__':main()
