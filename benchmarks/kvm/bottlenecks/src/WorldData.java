import java.io.DataInputStream;

/* Parse the actual resource prefix; no synthetic map geometry or save claimed. */
final class WorldData implements Constants {
    MapData maps;
    int width, height, inmates, guards, fightFreq;
    int[] zones;
    short[][] objects;
    short[] seats;
    int[][] objectQueries, zoneQueries;

    static WorldData load(String name) throws Exception {
        WorldData w = new WorldData();
        w.maps = MapData.load(name);
        w.width = w.maps.paths.width;
        w.height = w.maps.paths.height;
        DataInputStream in = new DataInputStream(w.getClass().getResourceAsStream("/" + name));
        if (in.readInt() != 5) throw new RuntimeException("Unsupported resource version");
        in.readByte(); in.readUTF(); in.readUTF();
        in.readByte(); w.fightFreq = in.readByte(); in.readByte();
        if (in.readUnsignedByte() != w.width || in.readUnsignedByte() != w.height) throw new RuntimeException("Fixture size");
        w.inmates = in.readUnsignedByte(); w.guards = in.readUnsignedByte();
        skip(in, 4 + COUNT_JOBS - 1); // spawn XY, initial job, job count, flags
        int count = in.readByte();
        w.zones = new int[1 + count * 5]; w.zones[0] = count;
        for (int i = 0; i < count; ++i) {
            int p = i * 5 + 1;
            for (int k = 0; k < 4; ++k) w.zones[p + k] = in.readShort();
            w.zones[p + 4] = in.readByte();
        }
        for (int layer = 0; layer < 4; ++layer) skip(in, in.readUnsignedShort());
        w.objects = new short[4][];
        int seats = 0;
        for (int layer = 0; layer < 4; ++layer) {
            count = in.readUnsignedShort();
            short[] objects = w.objects[layer] = new short[1 + (count << 2)]; objects[0] = (short) count;
            for (int i = 0; i < count; ++i) {
                int p = i << 2;
                int obj = objects[p + 1] = (short) in.readUnsignedByte();
                objects[p + 2] = in.readShort();
                objects[p + 3] = (short) in.readUnsignedByte();
                objects[p + 4] = (short) in.readUnsignedByte();
                if (layer == 0 && (obj == Objects.CHAIR || obj == Objects.TRAINING_WEIGHT || obj == Objects.TRAINING_TREADMILL)) ++seats;
            }
        }
        in.close();
        w.seats = new short[1 + (seats << 1)];
        short[] ground = w.objects[0];
        for (int i = 0; i < ground[0]; ++i) {
            int p = i << 2, obj = ground[p + 1];
            if (obj != Objects.CHAIR && obj != Objects.TRAINING_WEIGHT && obj != Objects.TRAINING_TREADMILL) continue;
            int s = (w.seats[0]++ << 1) + 1;
            w.seats[s] = (short) ((ground[p + 3] & 255) | (ground[p + 4] << 8));
            w.seats[s + 1] = -1;
        }
        w.objectQueries = new int[256][3];
        w.zoneQueries = new int[256][3];
        for (int i = 0; i < 256; ++i) {
            int layer = i & 3;
            short[] objects = w.objects[layer];
            int p = objects[0] == 0 ? 0 : ((i * 47) % objects[0]) << 2;
            w.objectQueries[i][0] = objects[0] == 0 ? i % w.width : objects[p + 3] + (i % 3 - 1);
            w.objectQueries[i][1] = objects[0] == 0 ? i % w.height : objects[p + 4] - (i % 3);
            w.objectQueries[i][2] = layer;
            if ((i & 7) == 0) { w.objectQueries[i][0] = -7; w.objectQueries[i][1] = w.height + 5; }
            NPC npc = w.maps.paths.chars[i % w.maps.paths.active];
            w.zoneQueries[i][0] = npc.x + 7;
            w.zoneQueries[i][1] = npc.y + 7;
            w.zoneQueries[i][2] = i % (ZONE_SAFE + 1);
        }
        return w;
    }

    Actor[] actors(String variant, PerfGame map) {
        Actor[] actors = new Actor[maps.paths.active];
        for (int i = 0; i < actors.length; ++i) {
            NPC spawn = maps.paths.chars[i];
            Actor a = Factories.actor(variant);
            a.map = map; a.id = i; a.name = "NPC" + i;
            a.x = spawn.x; a.y = spawn.y;
            a.inmate = i <= inmates; a.guard = i > inmates && i <= inmates + guards;
            a.aiState = Actor.AI_WAYPOINT; a.correctPath = true;
            actors[i] = a;
        }
        map.chars = actors;
        return actors;
    }

    private static void skip(DataInputStream in, int n) throws Exception {
        for (int i = 0; i < n; ++i) in.readByte();
    }
}
