"""Offline supplement tests; no Java, VM, network, or real-index edits."""
import copy
import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import candidates as c
import run_bottlenecks as primary
sys.path.insert(0,str(c.HERE/'fallback'))
import run_fallback as fallback
sys.path.insert(0,str(c.HERE/'priority'))
import run_priority as priority
import conservative


def rows(module,samples=2):
    scenario='perks:'+('guard-failure' if module is fallback else 'npc')
    data=[]
    for sample in range(samples):
        for position,index in enumerate(primary.order_for(sample,len(module.NAMES))):
            name=module.NAMES[index]
            data.append(dict(engine='original-kvm-1.1',family='fallback' if module is fallback else 'priority',scenario=scenario,variant=name,sample=str(sample),order=str(position),iterations='2',operations='8',elapsed_ms='40' if name.endswith(('once','key')) else '80',checksum='7'))
    return data


class SupplementAnalysisTests(unittest.TestCase):
    def test_reject_incomplete_corrupt_and_unnormalized_data(self):
        for module in (fallback,priority):
            good=rows(module);bad=[[],good[:-1],good+[good[0]]]
            for field,value in (('elapsed_ms','0'),('operations','7'),('operations','16'),('order','99'),('checksum','8'),('engine','pspkvm'),('variant','unknown'),('sample','-1'),('scenario','unknown:npc'),('scenario','perks:unknown'),('family','path')):
                data=copy.deepcopy(good);data[0][field]=value;bad.append(data)
            data=copy.deepcopy(good);data[0]['unexpected']='field';bad.append(data)
            for data in bad:
                with self.subTest(module=module.__name__,data=data),self.assertRaises(ValueError):module.validate(data,2)

    def test_paired_median_not_ratio_of_medians(self):
        for module,reference,candidate in ((fallback,'heap-original','heap-once'),(priority,'decrease','decrease-key')):
            data=rows(module)
            for row in data:
                if row['sample']=='1':row['elapsed_ms']='20' if row['variant']==reference else '80'
            with tempfile.TemporaryDirectory() as directory:
                result=module.analyze(data,Path(directory),2)
                row=next(r for r in result if r['reference']==reference and r['candidate']==candidate)
                self.assertEqual(row['speedup_median'],1.125)
                self.assertAlmostEqual(row['time_reduction_percent'],100*(1-1/1.125))

    def test_csv_roundtrip_reanalysis_byte_identical(self):
        for module in (fallback,priority):
            with tempfile.TemporaryDirectory() as directory:
                directory=Path(directory);data=rows(module,10)
                module.analyze(data,directory/'a',10)
                primary.write_csv(directory/'raw.csv',primary.RAW_FIELDS,data)
                with (directory/'raw.csv').open() as stream:module.analyze(list(csv.DictReader(stream)),directory/'b',10)
                for name in ('summary.csv','paired.csv','calculations.md'):
                    self.assertEqual((directory/'a'/name).read_bytes(),(directory/'b'/name).read_bytes())

    def test_supplement_rotation_balances_slots(self):
        for n in (4,5):
            order=[primary.order_for(i,n) for i in range(2*n)]
            for candidate in range(n):
                for position in range(n):self.assertEqual(sum(r[position]==candidate for r in order),2)


class SupplementSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.states=c.variants()

    def test_fallback_changes_exactly_two_operands_only(self):
        old=self.states['heap'];new=dict(old);fallback.transform(new)
        self.assertEqual(new['src/Game.java'],old['src/Game.java'])
        self.assertEqual(new['common/src/Constants.java'],old['common/src/Constants.java'])
        self.assertEqual(new['src/NPC.java'].count('|| (inmate && map.pathfind('),2)
        oldbody=c.base.method(old['src/NPC.java'],'void tickAI(');newbody=c.base.method(new['src/NPC.java'],'void tickAI(')
        self.assertEqual(oldbody.count('rng.nextInt('),newbody.count('rng.nextInt('))
        self.assertIn('|| (inmate && map.pathfind(',fallback.expression(new))
        changed=[(a,b) for a,b in zip(old['src/NPC.java'].splitlines(),new['src/NPC.java'].splitlines()) if a!=b]
        self.assertEqual(len(old['src/NPC.java'].splitlines()),len(new['src/NPC.java'].splitlines()))
        self.assertEqual(len(changed),2)
        for a,b in changed:
            self.assertEqual(b,a.replace('|| map.pathfind(','|| (inmate && map.pathfind(').replace('false, path)) {','false, path))) {'))

    def test_priority_requires_decrease_hook_and_preserves_scope(self):
        old=self.states['decrease'];new=dict(old);priority.transform(new)
        self.assertEqual(new['src/NPC.java'],old['src/NPC.java'])
        self.assertEqual(new['common/src/Constants.java'],old['common/src/Constants.java'])
        a,b=old['src/Game.java'],new['src/Game.java']
        for marker,index in (('\t// region Pathfinding\n',0),('\t// endregion Pathfinding',1)):
            self.assertEqual(a.split(marker,1)[index],b.split(marker,1)[index])
        for signature in ('void openAdd(','void openImprove('):
            self.assertIn('priority[n] = nodeG[n] + nodeH[n]',c.base.method(b,signature))
        self.assertNotIn('g[',c.base.method(b,'void openRemove('))
        self.assertIn('private int[] openHeapPriority;',b)
        with self.assertRaises(ValueError):priority.transform(dict(self.states['heap']))

    def test_transforms_fail_closed(self):
        for fn in (fallback.transform,priority.transform):
            with self.assertRaises(ValueError):fn({p:'unknown source' for p in c.FILES})

    def test_conservative_excludes_optional_regressions(self):
        # Build expected state without writing any output.
        state=c.heap_base()
        for _,_,name,fn in c.SPECS:
            if name not in ('memo','facing'):fn(state)
        fallback.transform(state)
        heap=self.states['heap']
        for signature in ('void moveTowards(','boolean isInZone('):
            self.assertEqual(c.base.method(state['src/NPC.java'],signature),c.base.method(heap['src/NPC.java'],signature))
        self.assertNotIn('zoneCacheChecked',state['src/NPC.java'])
        self.assertIn('if (guard || attack)',state['src/NPC.java'])
        self.assertIn('LOGGING = false',state['common/src/Constants.java'])

    def test_all_supplement_exports_reproducible_private_and_reversible(self):
        source={p:(c.ROOT/p).read_bytes() for p in c.FILES}
        index=subprocess.check_output(['git','diff','--cached','--binary'],cwd=c.ROOT)
        for _ in range(2):
            fallback.export();priority.states_and_export();conservative.states_and_export()
            files=[p for p in c.PATCHES.rglob('*.patch')]
            actual={p:p.read_bytes() for p in files}
            if _==0:expected=actual
            else:self.assertEqual(actual,expected)
        self.assertEqual(index,subprocess.check_output(['git','diff','--cached','--binary'],cwd=c.ROOT))
        self.assertEqual(source,{p:(c.ROOT/p).read_bytes() for p in c.FILES})


if __name__=='__main__':unittest.main()
