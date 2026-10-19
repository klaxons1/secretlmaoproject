import java.io.DataInputStream;
import java.io.InputStream;

/* Read only the committed map prefix used by Game.loadMap/initMap.
 * No textures, proprietary external assets, saves, or random stash deletion.
 */
final class Fixtures implements Constants {
    static final String[] MAPS = {
        "perks", "stalagflucht", "shanktonstatepen", "jungle", "sanpancho", "irongate"
    };
    String name;
    int width, height, active;
    NPC[] chars;
    byte[] ground;
    int[] walkable;

    static Fixtures load(String name) throws Exception {
        Fixtures f = new Fixtures();
        f.name = name;
        InputStream resource = f.getClass().getResourceAsStream("/" + name);
        if (resource == null) throw new RuntimeException("Missing map: " + name);
        DataInputStream in = new DataInputStream(resource);
        if (in.readInt() != 5) throw new RuntimeException("Unsupported map version");
        in.readByte(); // map ID
        in.readUTF(); // tileset
        in.readUTF(); // ground image
        skip(in, 3); // NPC level, fight frequency, map type
        f.width = in.readUnsignedByte();
        f.height = in.readUnsignedByte();
        int inmates = in.readUnsignedByte();
        int guards = in.readUnsignedByte();
        int spawnX = in.readUnsignedByte(), spawnY = in.readUnsignedByte();
        skip(in, 2 + COUNT_JOBS - 1); // starting job, job count, availability
        skip(in, in.readUnsignedByte() * 9); // zones

        f.ground = new byte[f.width * f.height];
        for (int layer = 0; layer < 4; ++layer) {
            int count = in.readUnsignedShort();
            for (int i = 0; i < count; ++i) {
                byte tile = in.readByte();
                if (layer == 0) f.ground[i] = Collision.getTileCollision(tile);
            }
        }
        for (int layer = 0; layer < 4; ++layer) {
            int count = in.readUnsignedShort();
            for (int i = 0; i < count; ++i) {
                int object = in.readUnsignedByte();
                short sprite = in.readShort();
                int x = in.readUnsignedByte(), y = in.readUnsignedByte();
                if (layer != 0) continue;
                byte collision = Collision.getObjectCollision(object);
                if (collision == COLL_NONE) continue;
                for (int y2 = y - ((sprite & (3 << 10)) >> 10); y > y2; --y) {
                    for (int x2 = 0; x2 < ((sprite & (3 << 8)) >> 8); ++x2) {
                        int p = x + x2 + y * f.width;
                        if (f.ground[p] == COLL_SOLID &&
                                (collision == COLL_SOLID_INTERACT || collision == COLL_DETECTOR)) continue;
                        f.ground[p] = collision;
                    }
                }
            }
        }
        skip(in, in.readUnsignedShort() * 2); // lights
        skip(in, in.readUnsignedShort() * 2); // top-object indices
        for (int i = 0; i < 10; ++i) skip(in, in.readUnsignedShort() * 2); // waypoints
        skip(in, in.readUnsignedShort() * 3); // gym positions
        f.chars = new NPC[inmates + guards + 16];
        int count = in.readUnsignedShort(), addedInmates = 0, addedGuards = 0, n = 1;
        for (int i = 0; i < count; ++i) {
            int object = in.readUnsignedByte();
            int x = in.readUnsignedByte(), y = in.readUnsignedByte();
            switch (object) {
                case Objects.PLAYER_BED:
                    f.chars[0] = new NPC(0, x * TILE_SIZE, y * TILE_SIZE + 2, NPC.ANIM_LYING);
                    break;
                case Objects.BED:
                    if (addedInmates < inmates - 1) {
                        f.chars[n] = new NPC(n, x * TILE_SIZE, (y - 1) * TILE_SIZE + 2, NPC.ANIM_LYING);
                        ++n;
                        ++addedInmates;
                    }
                    break;
                case Objects.AI_WP_GUARD_GENERAL:
                    if (addedGuards < guards) {
                        f.chars[n] = new NPC(n, x * TILE_SIZE, y * TILE_SIZE, NPC.ANIM_REGULAR);
                        ++n;
                        ++addedGuards;
                    }
                    break;
                case Objects.AI_WP_DOCTOR_WORK:
                case Objects.AI_WP_EMPLOYMENT_OFFICER:
                    f.chars[n] = new NPC(n, spawnX * TILE_SIZE, spawnY * TILE_SIZE, NPC.ANIM_REGULAR);
                    ++n;
                    break;
                case Objects.PRISON_SNIPER:
                case Objects.JUNGLE_CHECKPOINT_GUARD:
                    f.chars[n] = new NPC(n, x * TILE_SIZE, y * TILE_SIZE, NPC.ANIM_REGULAR);
                    ++n;
                    break;
            }
        }
        in.close();
        f.active = n;
        count = 0;
        for (int i = 0; i < f.ground.length; ++i) {
            if ((f.ground[i] & COLL_BIT_SOLID_AI) == 0) ++count;
        }
        f.walkable = new int[count];
        count = 0;
        for (int i = 0; i < f.ground.length; ++i) {
            if ((f.ground[i] & COLL_BIT_SOLID_AI) == 0) f.walkable[count++] = i;
        }
        return f;
    }

    // Fixed spatially varied queries on the real static collision geometry.
    int[][] queries(int count) {
        int[][] result = new int[count][6];
        for (int i = 0; i < count; ++i) {
            int start = walkable[(17 + i * 137) % walkable.length];
            int target = walkable[(walkable.length / 2 + i * 251) % walkable.length];
            result[i][0] = start % width;
            result[i][1] = start / width;
            result[i][2] = i & 3;
            result[i][3] = target % width;
            result[i][4] = target / width;
            result[i][5] = i & 1;
        }
        return result;
    }

    private static void skip(DataInputStream in, int count) throws Exception {
        for (int i = 0; i < count; ++i) in.readByte();
    }
}
