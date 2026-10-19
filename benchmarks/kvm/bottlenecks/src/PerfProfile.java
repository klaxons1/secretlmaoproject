/* Separate operation-count run; these instrumented kernels are never timed. */
public final class PerfProfile {
    public static void main(String[] args)throws Exception {
        PerfBench.Trial trial=new PerfBench.Trial("path",args[0]);
        int expected=0;
        for(int i=0;i<Factories.PATH_NAMES.length;++i) {
            String name=Factories.PATH_NAMES[i];
            trial.prepare(name,true);trial.game.resetCounts();trial.run(1);
            if(i==0)expected=trial.hash;else if(trial.hash!=expected)throw new RuntimeException("Counted checksum mismatch");
            PerfGame g=trial.game;
            System.out.println("COUNT,"+args[0]+","+name+","+trial.units+","+g.expanded+","+g.heuristics+","+
                g.adds+","+g.removes+","+g.improves+","+g.peak+","+trial.found+","+trial.hash);
        }
    }
}
