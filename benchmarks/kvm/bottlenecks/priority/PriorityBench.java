/* Same timed path run-loop as primary suite, with separate cache variants. */
public final class PriorityBench {
    static void prepare(PerfBench.Trial task,String name) {
        task.game=PriorityFactories.game(name);task.game.load(task.data);
        task.game.init(task.data.width,task.data.height,task.data.maps.paths.ground);
        task.hash=0;task.found=0;
    }
    static long measure(PerfBench.Trial task,int n){long start=System.currentTimeMillis();task.run(n);return System.currentTimeMillis()-start;}
    public static void main(String[]args)throws Exception {
        String scenario=args[0];int samples=Integer.parseInt(args[1]),target=Integer.parseInt(args[2]);
        String[]names=PriorityFactories.PATH_NAMES;PerfBench.Trial task=new PerfBench.Trial("path",scenario);
        int[]iterations=new int[names.length];int expected=0;
        for(int k=0;k<names.length;++k) {
            System.gc();prepare(task,names[k]);task.run(2);
            if(k==0)expected=task.hash;else PriorityChecks.require(task.hash==expected,"Priority warmup checksum");
            int n=1;while(measure(task,n)<target&&n<(1<<25))n<<=1;iterations[k]=n;
        }
        for(int sample=0;sample<samples;++sample)for(int position=0;position<names.length;++position) {
            int j=sample%(names.length*2)<names.length?position:names.length-1-position,k=(j+sample%names.length)%names.length;
            System.gc();prepare(task,names[k]);task.run(2);long elapsed=measure(task,iterations[k]);
            PriorityChecks.require(elapsed>0&&task.hash==expected,"Priority measured checksum/time");
            System.out.println("RESULT,priority,"+scenario+","+names[k]+","+sample+","+position+","+iterations[k]+","+((long)iterations[k]*task.units)+","+elapsed+","+task.hash);
        }
    }
}

final class PriorityExtra {
    static void checkAnyKeys() {
        PerfGame a=PriorityFactories.game("decrease"),b=PriorityFactories.game("decrease-key");
        int size=257;a.init(size,1,new byte[size]);b.init(size,1,new byte[size]);boolean[]present=new boolean[size];
        for(int step=0;step<30000;++step) {
            int n=PriorityChecks.random(size);
            if(!present[n]) {
                a.nodeG[n]=b.nodeG[n]=(short)PriorityChecks.random(65536);
                a.nodeH[n]=b.nodeH[n]=(short)PriorityChecks.random(65536);
                a.openAdd(n);b.openAdd(n);present[n]=true;
            } else if(PriorityChecks.random(3)==0) {
                a.openRemove(n);b.openRemove(n);present[n]=false;
            } else {
                // Increases, decreases, signed overflow in G/H, and ties.
                // A removed node's previous cached F must not be used to repair
                // the remaining frontier after the caller changed its G/H.
                a.nodeG[n]=b.nodeG[n]=(short)PriorityChecks.random(65536);
                a.nodeH[n]=b.nodeH[n]=(short)PriorityChecks.random(65536);
                a.openRemove(n);b.openRemove(n);a.openAdd(n);b.openAdd(n);
            }
            PriorityChecks.queueState(a,b,present);
        }
        while(a.sortedNode!=-1){int n=a.sortedNode;a.openRemove(n);b.openRemove(n);present[n]=false;PriorityChecks.queueState(a,b,present);}
        System.out.println("CHECKS,arbitrary-rekey-states,30000+drain");
    }
}
