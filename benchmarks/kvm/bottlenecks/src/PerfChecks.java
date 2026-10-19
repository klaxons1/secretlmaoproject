/* Differential checks, not timed. Compare buffers/state/RNG, not only lengths. */
public final class PerfChecks implements Constants {
    static int seed=1234567,paths,queueStates,lookups,motions,visionCases;
    static int random(int n){seed=seed*1664525+1013904223;return(seed>>>1)%n;}
    static void require(boolean ok,String message){if(!ok)throw new RuntimeException(message);}

    static void pathCase(PerfGame[] games,int[]q,int length) {
        short[] reference=null;
        boolean expected=false;
        for(int k=0;k<games.length;++k) {
            short[] result=length<0?null:new short[length];
            if(result!=null)for(int i=0;i<result.length;++i)result[i]=(short)(i*3+7);
            boolean found=games[k].pathfind(q[0],q[1],q[2],q[3],q[4],q[5]!=0,result);
            if(k==0){reference=result;expected=found;}
            else {
                require(found==expected,"Path return: "+Factories.PATH_NAMES[k]+",case="+paths);
                if(result!=null)for(int i=0;i<length;++i)require(result[i]==reference[i],"Exact path buffer");
                PerfGame a=games[0],b=games[k];
                require(a.sortedNode==b.sortedNode,"Remaining frontier minimum");
                for(int i=0;i<a.nodeG.length;++i) {
                    require(a.nodeParent[i]==b.nodeParent[i]&&a.nodeG[i]==b.nodeG[i]&&a.nodeH[i]==b.nodeH[i],"Parent/G/H cleanup");
                    require(a.visitedNodes[i]==b.visitedNodes[i],"Discovery order");
                    require(a.nodeDir[i]==b.nodeDir[i]&&a.nodeX[i]==b.nodeX[i]&&a.nodeY[i]==b.nodeY[i],"Expansion state");
                }
            }
            require(games[k].openHeapSize==0&&games[k].openHeapSerial==0,"Heap reset");
            for(int i=0;i<games[k].openHeapPosition.length;++i)require(games[k].openHeapPosition[i]==-1,"Position cleanup");
        }
        ++paths;
    }

    static PerfGame[] kernels(int w,int h,byte[]solid) {
        PerfGame[] games=new PerfGame[Factories.PATH_NAMES.length];
        for(int i=0;i<games.length;++i){games[i]=Factories.game(Factories.PATH_NAMES[i]);games[i].init(w,h,solid);}
        return games;
    }

    static void paths()throws Exception {
        int[] lengths={-1,0,1,2,3,4,9,40,400,1200};
        for(int m=0;m<Fixtures.MAPS.length;++m) {
            MapData data=MapData.load(Fixtures.MAPS[m]);
            PerfGame[] games=kernels(data.paths.width,data.paths.height,data.paths.ground);
            int[][] queries=data.paths.queries(80);
            for(int i=0;i<queries.length;++i) {
                if((i&7)==0){queries[i][3]=queries[i][0];queries[i][4]=queries[i][1];}
                if((i&15)==1)queries[i][2]=-1;
                if((i&15)==2)queries[i][2]=109;
                pathCase(games,queries[i],lengths[i%lengths.length]);
            }
            String[] distributions={"npc","spread","local"};
            for(int d=0;d<distributions.length;++d) {
                queries=data.queries(distributions[d]);
                for(int i=0;i<queries.length;++i)pathCase(games,queries[i],1200);
            }
            System.gc();
        }
        for(int map=0;map<4;++map) {
            int w=17,h=19;byte[] solid=new byte[w*h];
            for(int i=0;i<solid.length;++i) {
                int r=random(13);
                solid[i]=r<2?COLL_SOLID:r==2?COLL_DESK:r==3?COLL_DOOR_STAFF:COLL_NONE;
            }
            PerfGame[] games=kernels(w,h,solid);
            for(int i=0;i<128;++i) {
                int[]q={random(w),random(h),random(12)-2,random(w),random(h),i&1};
                pathCase(games,q,lengths[i%lengths.length]);
            }
        }
    }

    static void queueState(PerfGame a,PerfGame b,boolean[]present) {
        require(a.sortedNode==b.sortedNode&&a.openHeapSize==b.openHeapSize,"Decrease-key min/size");
        for(int i=0;i<present.length;++i) {
            require((a.openHeapPosition[i]!=-1)==present[i]&&(b.openHeapPosition[i]!=-1)==present[i],"Decrease-key membership");
            if(!present[i])continue;
            require(a.openHeapOrder[i]==b.openHeapOrder[i],"FIFO tickets");
            int p=b.openHeapPosition[i];require((b.openHeap[p]&65535)==i,"Heap inverse map");
            if(p>0) {
                int parent=b.openHeap[(p-1)>>>1]&65535;
                int f=b.nodeG[i]+b.nodeH[i],pf=b.nodeG[parent]+b.nodeH[parent];
                require(f>pf||f==pf&&b.openHeapOrder[i]>=b.openHeapOrder[parent],"Heap order");
            }
        }
        ++queueStates;
    }

    static void queues() {
        PerfGame a=Factories.game("heap"),b=Factories.game("decrease");
        int size=257;a.init(size,1,new byte[size]);b.init(size,1,new byte[size]);
        boolean[] present=new boolean[size];
        for(int step=0;step<25000;++step) {
            int n=random(size);
            if(!present[n]) {
                a.nodeG[n]=b.nodeG[n]=(short)(step<size?100:random(65536)-32768);
                a.nodeH[n]=b.nodeH[n]=(short)(step<size?0:random(65536)-32768);
                a.openAdd(n);b.openAdd(n);present[n]=true;
            } else if(random(4)==0) {
                a.openRemove(n);b.openRemove(n);present[n]=false;
            } else {
                int old=a.nodeG[n],next=old-1-random(400);
                if(next>=-32768) {
                    a.nodeG[n]=b.nodeG[n]=(short)next;
                    a.openRemove(n);a.openAdd(n);b.openImprove(n);
                }
            }
            queueState(a,b,present);
        }
        while(a.sortedNode!=-1){int n=a.sortedNode;a.openRemove(n);b.openRemove(n);present[n]=false;queueState(a,b,present);}
    }

    static void helpers()throws Exception {
        String[] names={"heap","objects","zones","memo","seats","core"};
        for(int m=0;m<Fixtures.MAPS.length;++m) {
            WorldData data=WorldData.load(Fixtures.MAPS[m]);
            PerfGame[] maps=new PerfGame[names.length];Actor[] actors=new Actor[names.length];
            for(int k=0;k<names.length;++k){maps[k]=Factories.game(names[k]);maps[k].load(data);actors[k]=Factories.actor(names[k]);actors[k].map=maps[k];}
            // Full padded grids on every layer, including boundary, misses,
            // overlapping/zero-size objects and first-match precedence.
            for(int layer=0;layer<4;++layer)for(int y=-2;y<data.height+2;++y)for(int x=-2;x<data.width+2;++x) {
                int expected=maps[0].getObjectIdxAt(x,y,layer);
                for(int k=1;k<maps.length;++k)require(maps[k].getObjectIdxAt(x,y,layer)==expected,"Object index/overlap");
                ++lookups;
            }
            for(int i=0;i<3000;++i) {
                int x=random(data.width*16+64)-32,y=random(data.height*16+64)-32,zone=random(24)-3;
                boolean expected=maps[0].isInZone(x,y,zone);
                int first=maps[0].findZone(zone);
                for(int k=1;k<maps.length;++k) {
                    require(maps[k].isInZone(x,y,zone)==expected,"Zone rectangles");
                    require(maps[k].findZone(zone)==first,"First duplicate zone");
                }
                for(int k=0;k<actors.length;++k){actors[k].x=x-7;actors[k].y=y-7;}
                for(int repeat=0;repeat<3;++repeat)for(int k=0;k<actors.length;++k)require(actors[k].isInZone(zone)==expected,"NPC zone cache");
                int sx=random(260)-2,sy=random(260)-2;
                int seat=maps[0].getSeatIndex(data.seats,sx,sy);
                for(int k=1;k<maps.length;++k)require(maps[k].getSeatIndex(data.seats,sx,sy)==seat,"Packed seat range");
                ++lookups;
            }
            // Replacing zones models map reload; old cache entries must expire.
            int[][] replacement={{0},{3,0,0,16,16,ZONE_CANTEEN,0,0,64,64,ZONE_CANTEEN,-9,-8,5,5,-1},data.zones};
            for(int r=0;r<replacement.length;++r) {
                for(int k=0;k<maps.length;++k)maps[k].zones=replacement[r];
                for(int zone=-1;zone<=ZONE_SAFE+1;++zone)for(int x=-10;x<70;x+=5) {
                    boolean expected=maps[0].isInZone(x,0,zone);
                    for(int k=1;k<maps.length;++k)require(maps[k].isInZone(x,0,zone)==expected&&maps[k].findZone(zone)==maps[0].findZone(zone),"Zone reload");
                    for(int k=0;k<actors.length;++k){actors[k].x=x-7;actors[k].y=-7;require(actors[k].isInZone(zone)==expected,"NPC reload");}
                    ++lookups;
                }
            }
            short[] synthetic={4,77,0,0,0,0,77,77,77,0,0,0,0,77,77,0,0};
            short[][] objectCases={null,{0},synthetic};
            for(int r=0;r<objectCases.length;++r) {
                for(int k=0;k<maps.length;++k)maps[k].objects=new short[][]{objectCases[r]};
                for(int x=-2;x<80;x+=7)for(int y=-2;y<80;y+=7) {
                    int expected=maps[0].getObjectIdxAt(x,y,0);
                    for(int k=1;k<maps.length;++k)require(maps[k].getObjectIdxAt(x,y,0)==expected,"Null/zero-size objects");++lookups;
                }
            }
            System.gc();
        }
    }

    static void movement() {
        Actor original=Factories.actor("heap"),changed=Factories.actor("facing"),combined=Factories.actor("core");
        Actor[] actors={original,changed,combined};
        float[] special={0f,-0f,-1f,Float.MIN_VALUE,-Float.MIN_VALUE,1e-25f,-1e-25f,Float.MAX_VALUE,-Float.MAX_VALUE,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY,Float.NaN};
        float[] speeds={0f,-0f,0.1f,1.7f,2.4f,2f,Float.POSITIVE_INFINITY,Float.NaN,-1f};
        for(int i=0;i<40000;++i) {
            float x,y;
            if(i<special.length*special.length){x=special[i/special.length];y=special[i%special.length];}
            else if((i&3)==0){x=Float.intBitsToFloat(seed=seed*1664525+1013904223);y=Float.intBitsToFloat(seed=seed*1664525+1013904223);}
            else {x=random(180000)/100f-100;y=random(170000)/100f-100;}
            float speed=speeds[i%speeds.length];int tx=random(1700)-50,ty=random(1600)-50;
            if((i&15)==0){tx=0;ty=0;}
            for(int k=0;k<actors.length;++k){Actor a=actors[k];a.x=17;a.y=23;a.xFloat=x;a.yFloat=y;a.moveTowards(tx,ty,speed);}
            for(int k=1;k<actors.length;++k){Actor a=actors[k];require(a.x==original.x&&a.y==original.y&&a.direction==original.direction,"Movement integers/direction");require(Float.floatToIntBits(a.xFloat)==Float.floatToIntBits(original.xFloat)&&Float.floatToIntBits(a.yFloat)==Float.floatToIntBits(original.yFloat),"Movement float bits at "+i);}
            ++motions;
        }
    }

    static void visions()throws Exception {
        String[] names={"heap","vision","core"};
        for(int m=0;m<Fixtures.MAPS.length;++m) {
            WorldData data=WorldData.load(Fixtures.MAPS[m]);
            PerfGame[]maps=new PerfGame[names.length];Actor[][]actors=new Actor[names.length][];
            for(int k=0;k<names.length;++k){maps[k]=Factories.game(names[k]);maps[k].load(data);actors[k]=data.actors(names[k],maps[k]);}
            int[]states={Actor.AI_WAYPOINT,Actor.AI_SLEEP,Actor.AI_ROAM,Actor.AI_IDLE,Actor.AI_ATTACK};
            for(int step=0;step<900;++step) {
                int n=1+random(actors[0].length-1),state=states[random(states.length)];
                boolean target=random(2)==0,correct=random(2)==0;
                int anger=random(3)==0?3:0;
                int actorSeed=random(1000000),expectedRandom=0;
                for(int k=0;k<names.length;++k) {
                    for(int i=0;i<actors[k].length;++i){actors[k][i].fighting=(i+step)%13==0?1:0;actors[k][i].health=(i+step)%17==0?0:15;}
                    Actor a=actors[k][n];a.aiState=state;a.targetReached=target;a.correctPath=correct;a.angerTimer=anger;a.aiWaitTimer=11;a.animation=3;a.chaseTarget=null;a.heatCalls=a.heatHash=0;a.lastHeatText=null;a.lastHeatAmount=0;
                    maps[k].note=maps[k].solitaryReason=0;Actor.rng.setSeed(actorSeed);a.visionCandidates();
                    int next=Actor.rng.nextInt();
                    if(k==0)expectedRandom=next;
                    else {
                        Actor b=actors[0][n];
                        require(next==expectedRandom,"Vision RNG consumption");
                        require(a.aiState==b.aiState&&a.animation==b.animation&&a.angerTimer==b.angerTimer&&a.aiWaitTimer==b.aiWaitTimer,"Vision AI state");
                        require((a.chaseTarget==null?-1:a.chaseTarget.id)==(b.chaseTarget==null?-1:b.chaseTarget.id),"Vision target precedence");
                        require(a.heatCalls==b.heatCalls&&a.heatHash==b.heatHash,"Vision heat/dialog calls");
                        require(a.lastHeatAmount==b.lastHeatAmount&&(a.lastHeatText==null?b.lastHeatText==null:a.lastHeatText.equals(b.lastHeatText)),"Exact heat/dialog arguments");
                        require(maps[k].note==maps[0].note&&maps[k].solitaryReason==maps[0].solitaryReason,"Guard wall-detection side effects");
                    }
                }
                ++visionCases;
            }
            // Force guard wall discovery with a genuine digged-wall obstacle.
            for(int k=0;k<names.length;++k){
                Actor a=actors[k][1],b=actors[k][2];a.guard=true;a.inmate=false;a.x=16*4;a.y=16*5;a.aiState=Actor.AI_WAYPOINT;a.correctPath=true;
                b.guard=false;b.health=15;b.x=16*7;b.y=16*5;
                maps[k].solid=new byte[][]{new byte[data.width*data.height]};maps[k].solid[0][5+5*data.width]=COLL_DIGGED_WALL;
                maps[k].note=maps[k].solitaryReason=0;a.visionCandidates();require(maps[k].note==NOTE_SOLITARY&&maps[k].solitaryReason==REASON_WALL,"Must not skip passive guards");
            }
            System.gc();
        }
    }

    public static void main(String[]args)throws Exception {
        queues();paths();helpers();movement();visions();
        System.out.println("CHECKS,decrease-key-queue-states,"+queueStates);
        System.out.println("CHECKS,six-way-exact-paths,"+paths);
        System.out.println("CHECKS,lookup-cases,"+lookups);
        System.out.println("CHECKS,bit-exact-movement,"+motions);
        System.out.println("CHECKS,vision-state-rng-cases,"+visionCases);
        System.out.println("CHECKS,PASS");
    }
}
