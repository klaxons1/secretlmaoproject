/* Timed production method bodies are uninstrumented. Setup/GC/I/O excluded. */
public final class PerfBench implements Constants {
    static String[] names(String family) {
        if (family.equals("path")) return Factories.PATH_NAMES;
        if (family.equals("tiles")) return new String[] {"heap","tile-index","tile-cull","all"};
        String candidate = family.equals("npc-zones") ? "memo" : family;
        return new String[] {"heap",candidate,"core"};
    }

    static final class Trial {
        String family, scenario;
        WorldData data;
        PerfGame game;
        Actor actor;
        Actor[] actors;
        int[][] queries;
        short[] result = new short[1200];
        int units, hash, found;
        TileKernel tiles;
        Graphics graphics;
        int[][] cameras;

        Trial(String family, String scenario) throws Exception {
            this.family=family; this.scenario=scenario;
            if (family.equals("facing")) { units=128; return; }
            int colon=scenario.indexOf(':');
            String name=colon==-1?scenario:scenario.substring(0,colon);
            data=WorldData.load(name);
            if (family.equals("path")) { queries=data.maps.queries(scenario.substring(colon+1)); units=queries.length; }
            else if (family.equals("objects")) { queries=data.objectQueries; units=queries.length; }
            else if (family.equals("zones")) { queries=data.zoneQueries; units=queries.length; }
            else if (family.equals("npc-zones")) units=128;
            else if (family.equals("seats")) units=256;
            else if (family.equals("vision")) {
                units=0;
                boolean guard=scenario.endsWith(":guard");
                for (int i=1;i<data.maps.paths.active;++i)
                    if (guard ? i>data.inmates && i<=data.inmates+data.guards : i<=data.inmates) ++units;
                if (units==0) throw new RuntimeException("No vision receivers");
            } else if (family.equals("tiles")) { cameras=data.maps.cameras(240,320);units=cameras.length; }
            else throw new RuntimeException("Unknown family");
        }

        void prepare(String variant, boolean counted) {
            game=counted?Factories.counted(variant):Factories.game(variant);
            if (data!=null)game.load(data);
            if (family.equals("path"))game.init(data.width,data.height,data.maps.paths.ground);
            else if (family.equals("vision")) actors=data.actors(variant,game);
            else if (family.equals("tiles")) {
                if (variant.equals("heap")) tiles=new OriginalTiles();
                else if (variant.equals("tile-index"))tiles=new IndexedTiles();
                else if (variant.equals("all"))tiles=new CulledTiles();
                else tiles=new CullOnlyTiles();
                tiles.init(data.maps,true);graphics=new Graphics(240,320);
            } else { actor=Factories.actor(variant);actor.map=game; }
            hash=0;found=0;
        }

        void run(int iterations) {
            for (int iteration=0;iteration<iterations;++iteration) {
                hash=1; found=0;
                if (family.equals("path")) {
                    for (int i=0;i<queries.length;++i) {
                        int[] q=queries[i];result[0]=0;
                        boolean ok=game.pathfind(q[0],q[1],q[2],q[3],q[4],q[5]!=0,result);
                        hash=31*hash+(ok?1:0);
                        if (ok) { ++found;for(int n=0;n<result[0];++n)hash=31*hash+result[n]; }
                    }
                } else if (family.equals("objects")) {
                    for(int i=0;i<queries.length;++i) {int[]q=queries[i];hash=31*hash+game.getObjectIdxAt(q[0],q[1],q[2]);}
                } else if (family.equals("zones")) {
                    for(int i=0;i<queries.length;++i) {int[]q=queries[i];hash=31*hash+(game.isInZone(q[0],q[1],q[2])?1:0);}
                } else if (family.equals("npc-zones")) {
                    boolean moving=scenario.endsWith(":moving");
                    for(int i=0;i<units;++i) {
                        int p=moving?i:0;
                        actor.x=data.maps.paths.chars[p%data.maps.paths.active].x;
                        actor.y=data.maps.paths.chars[p%data.maps.paths.active].y;
                        hash=31*hash+(actor.isInZone(i%(ZONE_SAFE+1))?1:0);
                    }
                } else if (family.equals("seats")) {
                    for(int i=0;i<units;++i) {
                        int n=data.seats[0],p=n==0?0:data.seats[((i%n)<<1)+1]&65535;
                        int x=(p&255)+(i%3-1),y=(p>>>8);
                        hash=31*hash+game.getSeatIndex(data.seats,x,y);
                    }
                } else if (family.equals("facing")) {
                    for(int i=0;i<units;++i) {
                        actor.xFloat=(i*79%1536)+0.125f;actor.yFloat=(i*47%1488)+0.625f;
                        float speed=scenario.equals("turn")?0f:scenario.equals("move")?2.4f:(i&3)==0?0f:2.4f;
                        actor.moveTowards(i*53%1536,i*83%1488,speed);
                        hash=31*hash+actor.x+actor.y+actor.direction;
                    }
                } else if (family.equals("vision")) {
                    boolean guard=scenario.endsWith(":guard");
                    for(int i=1;i<actors.length;++i) {
                        Actor a=actors[i];
                        if (guard?!a.guard:!a.inmate) continue;
                        // AI_WAYPOINT means attack=false, so no random numbers or
                        // allocations here. All guard wall-detection still runs.
                        a.visionCandidates();
                        hash=31*hash+a.aiState+a.angerTimer+a.heatHash;
                    }
                    hash=31*hash+game.note+game.solitaryReason;
                } else if (family.equals("tiles")) {
                    graphics.reset();
                    for(int i=0;i<cameras.length;++i)tiles.render(graphics,cameras[i][0],cameras[i][1],240,320,0);
                    hash=graphics.visibleRegions*31+graphics.visibleRects;
                }
            }
        }
    }

    static long measure(Trial task,int iterations) {
        long start=System.currentTimeMillis();task.run(iterations);return System.currentTimeMillis()-start;
    }

    public static void main(String[] args)throws Exception {
        String family=args[0],scenario=args[1];
        int samples=Integer.parseInt(args[2]),target=Integer.parseInt(args[3]);
        String[] names=names(family);
        Trial task=new Trial(family,scenario);
        int[] iterations=new int[names.length];
        int expected=0;
        for(int variant=0;variant<names.length;++variant) {
            System.gc();task.prepare(names[variant],false);task.run(2);
            if(variant==0)expected=task.hash;else if(task.hash!=expected)throw new RuntimeException("Warmup checksum mismatch: "+names[variant]);
            int n=1;long elapsed;
            while((elapsed=measure(task,n))<target && n<(1<<25))n<<=1;
            if(elapsed<=0)throw new RuntimeException("Timer calibration");
            iterations[variant]=n;
        }
        for(int sample=0;sample<samples;++sample) {
            for(int position=0;position<names.length;++position) {
                int j=sample%(names.length*2)<names.length?position:names.length-1-position;
                int variant=(j+sample%names.length)%names.length;
                System.gc();task.prepare(names[variant],false);task.run(2);
                long elapsed=measure(task,iterations[variant]);
                if(elapsed<=0||task.hash!=expected)throw new RuntimeException("Measured checksum/time mismatch: "+names[variant]);
                System.out.println("RESULT,"+family+","+scenario+","+names[variant]+","+sample+","+position+","+
                    iterations[variant]+","+((long)iterations[variant]*task.units)+","+elapsed+","+task.hash);
            }
        }
    }
}
