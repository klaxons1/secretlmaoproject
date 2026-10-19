import java.io.DataInputStream;

/* Additional fixtures for the uncommitted heap/tile experiment. */
final class MapData implements Constants {
    Fixtures paths;
    byte[][] tiles, solid;
    int[][] waypoints;
    Image atlas, ground, shadow;

    static MapData load(String name) throws Exception {
        MapData data = new MapData();
        data.paths = Fixtures.load(name);
        DataInputStream in = new DataInputStream(data.getClass().getResourceAsStream("/" + name));
        if (in.readInt() != 5) throw new RuntimeException("Map version");
        in.readByte();
        String atlas = in.readUTF(), ground = in.readUTF();
        skip(in, 3);
        int width = in.readUnsignedByte(), height = in.readUnsignedByte();
        if (width != data.paths.width || height != data.paths.height) throw new RuntimeException("Map dimensions");
        skip(in, 4); // inmates, guards, NPC spawn
        skip(in, 2 + COUNT_JOBS - 1);
        skip(in, in.readUnsignedByte() * 9);
        data.tiles = new byte[4][width * height];
        data.solid = new byte[4][width * height];
        for (int layer = 0; layer < 4; ++layer) {
            int count = in.readUnsignedShort();
            in.readFully(data.tiles[layer], 0, count);
            for (int i = 0; i < data.tiles[layer].length; ++i) {
                byte tile = data.tiles[layer][i];
                data.solid[layer][i] = layer == LAYER_UNDERGROUND ?
                        (tile == 100 ? COLL_NONE : COLL_SOLID) : Collision.getTileCollision(tile);
            }
        }
        for (int layer = 0; layer < 4; ++layer) {
            int count = in.readUnsignedShort();
            for (int i = 0; i < count; ++i) {
                int object = in.readUnsignedByte();
                short sprite = in.readShort();
                int x = in.readUnsignedByte(), y = in.readUnsignedByte();
                byte collision = Collision.getObjectCollision(object);
                if (collision == COLL_NONE) continue;
                for (int end = y - ((sprite & (3 << 10)) >> 10); y > end; --y) {
                    for (int dx = 0; dx < ((sprite & (3 << 8)) >> 8); ++dx) {
                        int p = x + dx + y * width;
                        if (data.solid[layer][p] == COLL_SOLID &&
                                (collision == COLL_SOLID_INTERACT || collision == COLL_DETECTOR)) continue;
                        data.solid[layer][p] = collision;
                    }
                }
            }
        }
        for (int i = 0; i < data.paths.ground.length; ++i) {
            if (data.solid[0][i] != data.paths.ground[i]) throw new RuntimeException("Collision fixture drift");
        }
        skip(in, in.readUnsignedShort() * 2);
        skip(in, in.readUnsignedShort() * 2);
        data.waypoints = new int[10][];
        for (int group = 0; group < data.waypoints.length; ++group) {
            int count = in.readUnsignedShort();
            data.waypoints[group] = new int[count];
            for (int i = 0; i < count; ++i) {
                int x = in.readUnsignedByte(), y = in.readUnsignedByte();
                data.waypoints[group][i] = x + y * width;
            }
        }
        in.close();
        data.atlas = Image.load(0, atlas);
        data.ground = Image.load(1, ground);
        data.shadow = Image.load(2, "/shadow.png");
        return data;
    }

    int[][] queries(String distribution) {
        if (distribution.equals("spread")) return paths.queries(8);
        int width = paths.width;
        int[][] result = new int[16][6];
        for (int i = 0; i < result.length; ++i) {
            int start, target;
            if (distribution.equals("npc")) {
                NPC npc = paths.chars[i % paths.active];
                start = npc.x / TILE_SIZE + ((npc.y + 5) / TILE_SIZE) * width;
                // Reachability-filtered NPC-like endpoints, NOT a captured game
                // workload. Keep legacy failures separately in "spread".
                boolean[] reachable = flood(start, (i & 1) != 0);
                target = -1;
                for (int g = 0; g < waypoints.length && target == -1; ++g) {
                    int[] group = waypoints[(i + g) % waypoints.length];
                    for (int p = 0; p < group.length; ++p) {
                        int candidate = group[(i * 7 + p) % group.length];
                        if (candidate != start && reachable[candidate]) { target = candidate; break; }
                    }
                }
                if (target == -1) {
                    for (int p = 0; p < paths.walkable.length; ++p) {
                        int candidate = paths.walkable[(i * 251 + 17 + p) % paths.walkable.length];
                        if (candidate != start && reachable[candidate]) { target = candidate; break; }
                    }
                }
                if (target == -1) target = start;
            } else if (distribution.equals("local")) {
                start = paths.walkable[(i * 137 + 17) % paths.walkable.length];
                target = start;
                int[] offsets = {1, -1, width, -width};
                for (int j = 0; j < offsets.length; ++j) {
                    int n = start + offsets[j];
                    if (n >= 0 && n < paths.ground.length && Math.abs(n % width - start % width) <= 1 &&
                            (paths.ground[n] & COLL_BIT_SOLID_AI) == 0) {
                        target = n;
                        break;
                    }
                }
            } else throw new RuntimeException("Unknown query distribution");
            result[i][0] = start % width;
            result[i][1] = start / width;
            result[i][2] = i & 3;
            result[i][3] = target % width;
            result[i][4] = target / width;
            result[i][5] = i & 1;
        }
        return result;
    }

    private boolean[] flood(int start, boolean noStaffDoors) {
        int width = paths.width, height = paths.height;
        byte[] collision = paths.ground;
        boolean[] seen = new boolean[collision.length];
        int[] queue = new int[collision.length];
        int head = 0, tail = 1;
        queue[0] = start;
        seen[start] = true;
        int[] dx = {1, 0, -1, 0, 1, 1, -1, -1};
        int[] dy = {0, -1, 0, 1, -1, 1, -1, 1};
        while (head < tail) {
            int p = queue[head++], x = p % width, y = p / width;
            for (int d = 0; d < dx.length; ++d) {
                int nx = x + dx[d], ny = y + dy[d];
                if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;
                int n = nx + ny * width;
                if (seen[n] || (collision[n] & COLL_BIT_SOLID_AI) != 0 || (noStaffDoors && collision[n] == COLL_DOOR_STAFF)) continue;
                if (d >= 4 && (((collision[x + ny * width] | collision[nx + y * width]) & COLL_BIT_SOLID_AI) != 0)) continue;
                seen[n] = true;
                queue[tail++] = n;
            }
        }
        return seen;
    }

    int[][] cameras(int width, int height) {
        int centerX = (paths.width * TILE_SIZE - width) / 2;
        int centerY = (paths.height * TILE_SIZE - height) / 2;
        return new int[][] {{0, 0}, {1, 7}, {15, 15}, {centerX, centerY}, {centerX + 7, centerY + 3},
                {paths.width * TILE_SIZE - width, paths.height * TILE_SIZE - height}, {-17, -1},
                {paths.width * TILE_SIZE - width + 15, paths.height * TILE_SIZE - height + 15}};
    }

    private static void skip(DataInputStream in, int count) throws Exception {
        for (int i = 0; i < count; ++i) in.readByte();
    }
}
