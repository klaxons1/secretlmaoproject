/* Supplemental caller benchmark; original expressions extracted from NPC.java. */
abstract class RequestBase implements Constants {
    PerfGame map;
    int x,y,direction,pathX,pathY,calls;
    boolean inmate;
    short[] path;
    abstract boolean request();
    boolean counted(int sx,int sy,int sd,int tx,int ty,boolean doors,short[]res) {
        ++calls;return map.pathfind(sx,sy,sd,tx,ty,doors,res);
    }
    void query(int[]q,boolean policy,short[]buffer) {
        x=q[0]*TILE_SIZE;y=q[1]*TILE_SIZE-5;direction=q[2];pathX=q[3];pathY=q[4];inmate=policy;path=buffer;calls=0;
    }
}

public final class FallbackBench implements Constants {
    static final String[] NAMES={"heap-original","heap-once","core-original","core-once"};
    static RequestBase make(String variant,WorldData world,boolean counted) {
        boolean once=variant.endsWith("once");
        RequestBase r=counted?(once?(RequestBase)new CountedOnceRequest():new CountedOriginalRequest()):
            (once?(RequestBase)new OnceRequest():new OriginalRequest());
        r.map=Factories.game(variant.startsWith("core")?"core":"heap");
        r.map.init(world.width,world.height,world.maps.paths.ground);
        return r;
    }
    static void require(boolean ok,String message){if(!ok)throw new RuntimeException(message);}

    static void state(PerfGame a,PerfGame b) {
        require(a.sortedNode==b.sortedNode,"Fallback remaining head");
        for(int i=0;i<a.nodeG.length;++i) {
            require(a.nodeG[i]==b.nodeG[i]&&a.nodeH[i]==b.nodeH[i]&&a.nodeParent[i]==b.nodeParent[i],"Fallback costs/cleanup");
            require(a.visitedNodes[i]==b.visitedNodes[i]&&a.nodeDir[i]==b.nodeDir[i]&&a.nodeX[i]==b.nodeX[i]&&a.nodeY[i]==b.nodeY[i],"Fallback exploration state");
            require(a.openHeapPosition[i]==-1&&b.openHeapPosition[i]==-1,"Fallback positions reset");
        }
    }

    static void check()throws Exception {
        int cases=0,skipped=0,retained=0;
        int[] lengths={-1,0,3,40,400,1200};
        for(int m=0;m<Fixtures.MAPS.length;++m) {
            WorldData world=WorldData.load(Fixtures.MAPS[m]);
            RequestBase[] requests=new RequestBase[NAMES.length];
            for(int k=0;k<requests.length;++k)requests[k]=make(NAMES[k],world,true);
            int[][]q=world.maps.paths.queries(32);
            for(int i=0;i<q.length;++i)for(int policy=0;policy<2;++policy) {
                boolean expected=false;short[] reference=null;int originalCalls=0;
                for(int k=0;k<requests.length;++k) {
                    int length=lengths[i%lengths.length];short[]result=length<0?null:new short[length];
                    if(result!=null)for(int p=0;p<result.length;++p)result[p]=(short)(p*3+7);
                    RequestBase r=requests[k];r.query(q[i],policy!=0,result);boolean ok=r.request();
                    if(k==0){expected=ok;reference=result;originalCalls=r.calls;}
                    else {
                        require(ok==expected,"Fallback boolean return");
                        if(result!=null)for(int p=0;p<result.length;++p)require(result[p]==reference[p],"Fallback partial/full result buffer");
                        state(requests[0].map,r.map);
                        if(k==1||k==3) {
                            PerfGame previous=requests[k-1].map;
                            require(previous.openHeapSize==r.map.openHeapSize&&previous.openHeapSerial==r.map.openHeapSerial,"Fallback heap scalar state");
                            for(int p=0;p<previous.nodeG.length;++p)
                                require(previous.openHeap[p]==r.map.openHeap[p]&&previous.openHeapPosition[p]==r.map.openHeapPosition[p]&&previous.openHeapOrder[p]==r.map.openHeapOrder[p],"Fallback entire heap scratch state");
                        }
                    }
                    if(policy==0&&!ok)require(r.calls==(k%2==0?2:1),"Only identical failed retry may be removed");
                    else require(r.calls==originalCalls,"Different door policy fallback must remain");
                }
                if(policy==0&&!expected)++skipped;else ++retained;
                ++cases;
            }
            System.gc();
        }
        // Validate the selected failure cohort too, including deliberately
        // blocked goals where the map has no sampled unreachable walkable goal.
        for(int m=0;m<Fixtures.MAPS.length;++m) {
            Trial t=new Trial(Fixtures.MAPS[m]+":guard-failure");
            RequestBase[]requests=new RequestBase[NAMES.length];
            for(int k=0;k<requests.length;++k)requests[k]=make(NAMES[k],t.world,true);
            for(int i=0;i<t.queries.length;++i) {
                short[]reference=null;
                for(int k=0;k<requests.length;++k) {
                    short[]buffer=new short[400];for(int p=0;p<buffer.length;++p)buffer[p]=(short)(p*3+7);
                    RequestBase r=requests[k];r.query(t.queries[i],false,buffer);
                    require(!r.request()&&r.calls==(k%2==0?2:1),"Failure fixture calls/result");
                    if(k==0)reference=buffer;
                    else {
                        for(int p=0;p<buffer.length;++p)require(buffer[p]==reference[p],"Failure fixture buffer");
                        state(requests[0].map,r.map);
                        if(k==1||k==3) {
                            PerfGame a=requests[k-1].map,b=r.map;
                            for(int p=0;p<a.nodeG.length;++p)
                                require(a.openHeap[p]==b.openHeap[p]&&a.openHeapPosition[p]==b.openHeapPosition[p]&&a.openHeapOrder[p]==b.openHeapOrder[p],"Failure fixture heap scratch");
                        }
                    }
                }
                ++cases;++skipped;
            }
            System.gc();
        }
        // A forced staff-door corridor proves that true->false fallback remains.
        WorldData world=WorldData.load("perks");byte[]solid=new byte[7*3];
        for(int i=0;i<solid.length;++i)solid[i]=COLL_SOLID;
        for(int x=0;x<7;++x)solid[x+7]=COLL_NONE;
        solid[3+7]=COLL_DOOR_STAFF;
        int[]q={0,1,0,6,1,1};
        for(int k=0;k<NAMES.length;++k) {
            RequestBase r=make(NAMES[k],world,true);r.map.init(7,3,solid);
            r.query(q,true,new short[400]);require(r.request()&&r.calls==2,"Needed staff-door fallback was removed");
        }
        System.out.println("CHECKS,four-way-fallback-cases,"+cases);
        System.out.println("CHECKS,non-inmate-false-cases,"+skipped);
        System.out.println("CHECKS,retained-control-cases,"+retained);
        System.out.println("CHECKS,forced-staff-fallback,4");
        System.out.println("CHECKS,PASS");
    }

    static final class Trial {
        WorldData world;
        int[][]queries;
        boolean policy;
        RequestBase request;
        int hash,calls,nativeSelected,blockedSelected;
        boolean[]blockedTarget=new boolean[8];
        short[]result=new short[400];
        Trial(String scenario)throws Exception {
            int colon=scenario.indexOf(':');world=WorldData.load(scenario.substring(0,colon));
            String distribution=scenario.substring(colon+1);policy=distribution.equals("inmate-policy");
            int[][] candidates=world.maps.paths.queries(128);
            queries=new int[8][];int n=0;
            PerfGame kernel=Factories.game("heap");kernel.init(world.width,world.height,world.maps.paths.ground);
            for(int i=0;i<candidates.length&&n<queries.length;++i) {
                int[]q=candidates[i];boolean found=kernel.pathfind(q[0],q[1],q[2],q[3],q[4],false,result);
                if(policy || found==distribution.equals("guard-success"))queries[n++]=q;
            }
            nativeSelected=n;
            if(distribution.equals("guard-failure")&&n<queries.length) {
                // Do not pretend failures are frequent: many shipped maps have
                // connected walkable geometry when staff doors are allowed.
                // Explicit conditional stress control: aim at a real solid cell,
                // without modifying the map. Export its classification per query.
                byte[]solid=world.maps.paths.ground;
                for(int p=0;p<solid.length&&n<queries.length;++p)if((solid[p]&COLL_BIT_SOLID_AI)!=0) {
                    int[]start=candidates[(n*13)%candidates.length];
                    int[]q={start[0],start[1],start[2],p%world.width,p/world.width,0};
                    require(!kernel.pathfind(q[0],q[1],q[2],q[3],q[4],false,result),"Blocked-goal control unexpectedly succeeded");
                    blockedTarget[n]=true;queries[n++]=q;++blockedSelected;
                }
            }
            if(n!=queries.length)throw new RuntimeException("Insufficient selected requests: "+scenario);
        }
        void prepare(String variant,boolean counted){request=make(variant,world,counted);hash=0;calls=0;}
        void run(int iterations) {
            for(int i=0;i<iterations;++i) {
                hash=1;calls=0;
                for(int j=0;j<queries.length;++j) {
                    result[0]=0;request.query(queries[j],policy,result);boolean ok=request.request();
                    calls+=request.calls;hash=31*hash+(ok?1:0);
                    if(ok)for(int p=0;p<result[0];++p)hash=31*hash+result[p];
                }
            }
        }
    }
    static long measure(Trial t,int iterations){long start=System.currentTimeMillis();t.run(iterations);return System.currentTimeMillis()-start;}

    public static void main(String[]args)throws Exception {
        if(args[0].equals("check")){check();return;}
        if(args[0].equals("fixtures")) {
            for(int m=0;m<Fixtures.MAPS.length;++m) {
                String[]distributions={"guard-failure","guard-success","inmate-policy"};
                for(int d=0;d<distributions.length;++d) {
                    String scenario=Fixtures.MAPS[m]+":"+distributions[d];Trial t=new Trial(scenario);
                    System.out.println("SELECT,"+scenario+","+t.nativeSelected+","+t.blockedSelected);
                    for(int i=0;i<t.queries.length;++i) {
                        int[]q=t.queries[i];System.out.println("QUERY,"+scenario+","+i+","+q[0]+","+q[1]+","+q[2]+","+q[3]+","+q[4]+","+(t.policy?1:0)+","+(t.blockedTarget[i]?1:0));
                    }
                }
            }
            return;
        }
        String scenario=args[1];int samples=Integer.parseInt(args[2]),target=Integer.parseInt(args[3]);
        Trial t=new Trial(scenario);int[]iterations=new int[NAMES.length];int expected=0;
        for(int k=0;k<NAMES.length;++k) {
            System.gc();t.prepare(NAMES[k],false);t.run(2);
            if(k==0)expected=t.hash;else require(t.hash==expected,"Fallback warmup checksum");
            int n=1;while(measure(t,n)<target&&n<(1<<25))n<<=1;iterations[k]=n;
        }
        for(int sample=0;sample<samples;++sample)for(int position=0;position<NAMES.length;++position) {
            int j=sample%8<4?position:3-position,k=(j+sample%4)%4;
            System.gc();t.prepare(NAMES[k],false);t.run(2);long elapsed=measure(t,iterations[k]);
            require(elapsed>0&&t.hash==expected,"Fallback measured checksum/time");
            System.out.println("RESULT,fallback,"+scenario+","+NAMES[k]+","+sample+","+position+","+iterations[k]+","+((long)iterations[k]*t.queries.length)+","+elapsed+","+t.hash);
        }
        for(int k=0;k<NAMES.length;++k) {
            t.prepare(NAMES[k],true);t.run(1);require(t.hash==expected,"Fallback counter checksum");
            System.out.println("CALLS,"+scenario+","+NAMES[k]+","+t.queries.length+","+t.calls+","+t.hash);
        }
    }
}
