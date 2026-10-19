"""Offline publication/analysis guards: no Java/network, real-index/worktree writes."""
import copy
import csv
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import candidates as c
import run_bottlenecks as runner


def rows(samples=2):
    result=[]
    for sample in range(samples):
        names=runner.NAMES['objects']
        for position,index in enumerate(runner.order_for(sample,len(names))):
            variant=names[index]
            result.append(dict(engine='original-kvm-1.1',family='objects',scenario='fixture',variant=variant,
                sample=str(sample),order=str(position),iterations='2',operations='8',elapsed_ms=str(80 if variant=='heap' else 40),checksum='7'))
    return result


class AnalysisTests(unittest.TestCase):
    def test_paired_not_ratio_of_medians(self):
        data=rows()
        for row in data:
            if row['sample']=='1': row['elapsed_ms']='20' if row['variant']=='heap' else '80'
        with tempfile.TemporaryDirectory() as directory:
            result=runner.analyze(data,Path(directory),2)
            # median(80/40,20/80) = 1.125, NOT 50/60.
            self.assertEqual(result[0]['speedup_median'],1.125)
            self.assertAlmostEqual(result[0]['time_reduction_percent'],100*(1-1/1.125))
            self.assertTrue((Path(directory)/'paired.csv').is_file())

    def test_rotation_balanced_and_unique(self):
        for n in (3,4,6):
            orders=[runner.order_for(i,n) for i in range(2*n)]
            self.assertTrue(all(sorted(x)==list(range(n)) for x in orders))
            for candidate in range(n):
                for position in range(n):self.assertEqual(sum(order[position]==candidate for order in orders),2)

    def test_reject_bad_raw_data(self):
        good=rows()
        bad=[[],good[:-1],good+[good[0]],good[1:]]
        for field,value in (('elapsed_ms','0'),('operations','7'),('order','99'),('checksum','8'),('engine','pspkvm'),('variant','unknown'),('sample','-1')):
            data=copy.deepcopy(good);data[0][field]=value;bad.append(data)
        for data in bad:
            with self.subTest(data=data),self.assertRaises(ValueError):runner.validate(data,2)

    def test_reanalysis_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            a,b=Path(directory)/'a',Path(directory)/'b'
            data=rows(6);runner.analyze(data,a)
            path=Path(directory)/'raw.csv';runner.write_csv(path,runner.RAW_FIELDS,data)
            with path.open() as stream:runner.analyze(list(csv.DictReader(stream)),b)
            for name in ('summary.csv','paired.csv','calculations.md'):self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())


class ExportTests(unittest.TestCase):
    def test_master_and_heap_pins(self):
        original=c.source(c.MASTER,'src/Game.java')
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),'f1d042561b1292898ff84f0a76af9984d30064179f4db7617333f0f12288d092')
        heap=c.heap_base()['src/Game.java']
        self.assertEqual(hashlib.sha256(heap.encode()).hexdigest(),'91b50cd8aee341d6c0350653b468a0e23c06d3b697287e8dff98c67bfc4ba107')

    def test_series_and_standalones_apply_reverse(self):
        runner.WORK.mkdir(parents=True,exist_ok=True)
        before={p:(c.ROOT/p).read_bytes() for p in c.FILES}
        index=subprocess.check_output(['git','diff','--cached','--binary'],cwd=c.ROOT)
        files=c.export();runner.verify_series(files)
        self.assertEqual(len(files),13)
        self.assertEqual(index,subprocess.check_output(['git','diff','--cached','--binary'],cwd=c.ROOT))
        for p in c.FILES:self.assertEqual((c.ROOT/p).read_bytes(),before[p])

    def test_export_is_reproducible(self):
        c.export()
        files=list(c.PATCHES.glob('*.patch'))+list((c.PATCHES/'standalone').glob('*.patch'))+[c.PATCHES/'series.txt']
        before={p:p.read_bytes() for p in files};c.export()
        self.assertEqual(before,{p:p.read_bytes() for p in files})

    def test_transforms_refuse_unknown_shapes(self):
        with self.assertRaises(ValueError):c.once('duplicate duplicate','duplicate','x')
        for number,label,name,fn in c.SPECS:
            with self.subTest(name=name),self.assertRaises((ValueError,IndexError,RuntimeError)):
                fn({path:'not the known source' for path in c.FILES})

    def test_scopes_and_no_schedule_or_sort_changes(self):
        states=c.variants();heap=states['heap']
        for name in ('heuristic','diagonal','stepcost','decrease'):
            game=states[name]['src/Game.java'];reference=heap['src/Game.java']
            self.assertEqual(reference.split('\t// region Pathfinding\n')[0],game.split('\t// region Pathfinding\n')[0])
            self.assertEqual(reference.split('\t// endregion Pathfinding')[1],game.split('\t// endregion Pathfinding')[1])
        for name,state in states.items():
            if name=='diagnostic':continue
            self.assertEqual(c.base.method(state['src/Game.java'],'void tickMap('),c.base.method(heap['src/Game.java'],'void tickMap('))
            self.assertEqual(c.base.method(state['src/Game.java'],'static void sortRenderChars('),c.base.method(heap['src/Game.java'],'static void sortRenderChars('))

    def test_vision_keeps_guard_and_rng_path(self):
        old=c.base.method(c.heap_base()['src/NPC.java'],'void tickAI(')
        state=c.heap_base();c.vision(state)
        new=c.base.method(state['src/NPC.java'],'void tickAI(')
        self.assertIn('if (guard || attack) {',new)
        self.assertEqual(old.count('rng.nextInt('),new.count('rng.nextInt('))
        self.assertEqual(old.count('!canSee(other)'),new.count('!canSee(other)'))
        self.assertEqual(old.split('boolean found = false;')[0],new.split('boolean found = false;')[0])
        self.assertEqual(old.split('if (attack && found)')[1],new.split('if (attack && found)')[1])


if __name__=='__main__':unittest.main()
