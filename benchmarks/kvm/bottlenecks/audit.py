#!/usr/bin/env python3
"""Offline publication audit; optionally also verify ignored build-cache bytes."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import candidates as c
import run_bottlenecks as primary
sys.path.insert(0,str(c.HERE/'fallback'))
import run_fallback as fallback
sys.path.insert(0,str(c.HERE/'priority'))
import run_priority as priority
import conservative

base=c.base
ROOT=c.ROOT
checks=0


def require(condition,message):
    global checks
    if not condition:raise ValueError(message)
    checks+=1


def json_at(path):return json.loads(path.read_text())


def rows_at(path):
    with path.open() as stream:return list(csv.DictReader(stream))


def hash_at(path,expected):
    require(path.is_file(),'Missing file: '+str(path))
    require(base.sha(path.read_bytes())==expected,'Hash mismatch: '+str(path))


def reanalyze(module,directory,samples):
    rows=rows_at(directory/'raw.csv')
    with tempfile.TemporaryDirectory() as output:
        if module is primary:module.analyze(rows,Path(output),samples)
        else:module.analyze(rows,Path(output),samples)
        for name in ('summary.csv','paired.csv','calculations.md'):
            require((Path(output)/name).read_bytes()==(directory/name).read_bytes(),'Reanalysis mismatch: '+str(directory/name))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--with-build-cache',action='store_true');args=parser.parse_args()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip()
    print('Audit checkout branch:',branch)
    for directory in ('src','common/src'):
        for path in sorted((ROOT/directory).glob('*.java')):
            require(path.read_text()==c.source(c.MASTER,str(path.relative_to(ROOT))),'Production modified: '+str(path))
    print('PASS production sources match pinned master; no runtime patch auto-applied')
    historical=c.PARENT/'experiments/results/raw.csv'
    hash_at(historical,'e8da9b31591e32dcef858c885ac7a9ef7e2c5318f656ef5f3c86e69d5cbd104d')
    require(len(rows_at(historical))==2484,'Historical experiment interval count')
    original=c.PARENT/'results/raw.csv'
    original_at_publication=subprocess.check_output(['git','show','b3dee4bbb5834d44e46c63af16d8a9214dbb5bf4:benchmarks/kvm/results/raw.csv'],cwd=ROOT)
    require(original.read_bytes()==original_at_publication,'Original historical raw replaced')
    require(len(rows_at(original))==378,'Original historical interval count')
    require(len(rows_at(c.PARENT/'experiments/results/awt-controlled/raw.csv'))==162,'Separate historical AWT count')
    print('PASS historical raw preserved: 378 original / 2484 experiment / 162 separate AWT intervals')
    pe=json_at(primary.RESULTS/'environment.json')
    require(pe['kvm_sha256']==base.KVM_SHA256 and pe['kvm_heap_bytes']==2*1024*1024,'Original KVM pin/heap')
    require(not pe['pspkvm_tested_here'] and not pe['whole_game_profile'],'Benchmark scope flags')
    for name,expected in pe['input_sha256'].items():hash_at(ROOT/name,expected)
    for name,expected in pe['resources_sha256'].items():hash_at(ROOT/'res'/name,expected)
    for name,state in c.variants().items():
        for path,text in state.items():require(base.sha(text.encode())==pe['prototype_sha256'][name][path],'Primary prototype: '+name+' '+path)
    mainrows=reanalyze(primary,primary.RESULTS,pe['samples']);groups=primary.validate(mainrows,pe['samples'])
    require(set(groups)==set(primary.scenarios()),'Primary scenario coverage')
    require(len(mainrows)==3204 and len(rows_at(primary.RESULTS/'summary.csv'))==198,'Primary interval/summary count')
    require(len(pe['footprints'])==32,'Primary full-build count')
    if args.with_build_cache:
        hash_at(base.kvm_binary(),base.KVM_SHA256)
        for name,expected in pe['generated_java_sha256'].items():hash_at(primary.WORK/name,expected)
        for name,expected in pe['headless_class_sha256'].items():hash_at(primary.WORK/'verified'/name,expected)
        for label,footprint in pe['footprints'].items():
            for classname in ('Game','NPC','Constants'):
                path=primary.WORK/('game-'+label)/'verified'/(classname+'.class');hash_at(path,footprint[classname+'_sha256'])
                data=path.read_bytes();require(len(data)==footprint[classname+'_bytes'],'Primary class bytes')
                require(data[4:8]==b'\x00\x03\x00\x2d' and (classname=='Constants' or b'StackMap' in data),'Primary 45.3/StackMap')
    counts=rows_at(primary.RESULTS/'operation-counts.csv');require(len(counts)==108,'Primary counter count')
    for scenario in {r['scenario'] for r in counts}:
        group=[r for r in counts if r['scenario']==scenario]
        for field in ('queries','expanded','peak','found','checksum'):require(len({r[field] for r in group})==1,'Path counter equivalence '+field)
        by={r['variant']:r for r in group}
        require(int(by['heuristic']['heuristics'])<=int(by['heap']['heuristics']),'Deferred H count')
        require(by['core']['heuristics']==by['heuristic']['heuristics'],'Core H count')
        require(int(by['decrease']['adds'])+int(by['decrease']['improves'])==int(by['heap']['adds']),'Decrease removes reinsertion additions')
    print('PASS primary 3204 intervals / 69 scenarios / 32 complete builds; byte-identical reanalysis')
    total=3204
    extra_meta={}
    for module,expected_count in ((fallback,864),(priority,900)):
        directory=module.RESULTS;meta=json_at(directory/'environment.json');extra_meta[module]=meta
        require(meta['primary_environment_sha256']==base.sha((primary.RESULTS/'environment.json').read_bytes()),'Supplement primary provenance')
        require(meta['kvm_sha256']==base.KVM_SHA256 and not meta['pspkvm_tested_here'],'Supplement VM/scope')
        for name,expected in meta['input_sha256'].items():hash_at(ROOT/name,expected)
        rows=reanalyze(module,directory,meta['samples']);require(len(rows)==expected_count,'Supplement timing count')
        require(len(module.validate(rows,meta['samples']))==18,'Supplement six-map coverage')
        require(len(rows_at(directory/'summary.csv'))==54,'Supplement paired summary count')
        for name,expected in pe['headless_class_sha256'].items():require(meta['headless_class_sha256'][name]==expected,'Copied primary class changed')
        if args.with_build_cache:
            for name,expected in meta['source_sha256'].items():hash_at(ROOT/name,expected)
            for name,expected in meta['headless_class_sha256'].items():hash_at(module.WORK/'verified'/name,expected)
        total+=len(rows)
        print('PASS',module.__name__,len(rows),'intervals; separate fresh pairs and byte-identical reanalysis')
    calls=rows_at(fallback.RESULTS/'call-counts.csv');require(len(calls)==72,'Fallback call-count cells')
    for scenario in {r['scenario'] for r in calls}:
        group={r['variant']:r for r in calls if r['scenario']==scenario}
        require(len({r['checksum'] for r in group.values()})==1,'Fallback count checksums')
        require(all(int(r['requests'])==8 for r in group.values()),'Fallback request units')
        for a,b in (('heap-original','heap-once'),('core-original','core-once')):
            old,new=int(group[a]['path_calls']),int(group[b]['path_calls'])
            if scenario.endswith(':guard-failure'):require(old==16 and new==8,'Duplicate failed call not removed')
            elif scenario.endswith(':guard-success'):require(old==new==8,'Successful short circuit changed')
            else:require(old==new,'Different-door-policy fallback changed')
    fixtures=rows_at(fallback.RESULTS/'query-fixtures.csv');selection=rows_at(fallback.RESULTS/'fixture-selection.csv')
    require(len(fixtures)==144 and len(selection)==18,'Supplement fixture export completeness')
    require(sum(int(r['blocked_target']) for r in fixtures)==6,'Explicit blocked-target stress controls')
    for r in selection:
        group=[q for q in fixtures if q['scenario']==r['scenario']]
        blocked=sum(int(q['blocked_target']) for q in group)
        require(blocked==int(r['blocked_target_selected']) and len(group)-blocked==int(r['walkable_selected']),'Fixture classification')
    print('PASS fallback counts 16->8 on 8 failures, controls unchanged; 42 native-walkable/6 explicit blocked-target cases')
    ce=json_at(conservative.RESULTS/'environment.json');require(len(ce['footprints'])==4,'Conservative full-build count')
    for name,expected in ce['input_sha256'].items():hash_at(ROOT/name,expected)
    require(not ce['whole_combination_timed'] and ce['excluded_optional_patches']==['0011','0013'],'Conservative limitations')
    require(total==4968,'Total new interval count')
    require(len(extra_meta[fallback]['footprints'])==2 and len(extra_meta[priority]['footprints'])==3,'Supplement full-build counts')
    if args.with_build_cache:
        for module,meta,classname in ((fallback,extra_meta[fallback],'NPC'),(priority,extra_meta[priority],'Game')):
            for label,footprint in meta['footprints'].items():
                path=module.WORK/label/'verified'/(classname+'.class');hash_at(path,footprint[classname+'_sha256'])
                data=path.read_bytes();require(len(data)==footprint[classname+'_bytes'] and data[4:8]==b'\x00\x03\x00\x2d' and b'StackMap' in data,'Supplement full class verification')
        for label,footprint in ce['footprints'].items():
            for classname in ('Game','NPC'):
                path=conservative.WORK/label/'verified'/(classname+'.class');hash_at(path,footprint[classname+'_sha256'])
                data=path.read_bytes();require(len(data)==footprint[classname+'_bytes'] and data[4:8]==b'\x00\x03\x00\x2d' and b'StackMap' in data,'Conservative full class verification')
    print('PASS 41 full build/preverification records (32+2+3+4), not physical gameplay')
    summary=rows_at(primary.RESULTS/'summary.csv')
    require(all(float(r['speedup_median'])<1 for r in summary if r['candidate']=='memo' and r['scenario'].endswith(':moving')),'Moving regression must not be hidden')
    require(next(float(r['speedup_median']) for r in summary if r['candidate']=='facing' and r['scenario']=='move')<1,'Movement regression must not be hidden')
    print('PASS regression controls retained; optional 0011/0013 excluded from conservative')
    print('PASS all new data:',total,'intervals; no historical raw rewritten')
    print('PASS audit checks:',checks,'(build cache '+('verified' if args.with_build_cache else 'not requested')+')')


if __name__=='__main__':main()
