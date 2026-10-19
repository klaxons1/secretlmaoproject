/* Differential checks for all three frontier representations and tile phases. */
public final class ExperimentChecks implements Constants {
    private static int seed = 0x5a92e17b;
    private static int queueStates, paths, tileFrames;

    public static void main(String[] args) throws Exception {
        checkQueue();
        checkPaths();
        checkTiles();
        System.out.println("CHECKS,heap-queue-states," + queueStates);
        System.out.println("CHECKS,three-way-exact-paths," + paths);
        System.out.println("CHECKS,three-way-visible-tile-traces," + tileFrames);
        System.out.println("CHECKS,PASS");
    }

    private static int random(int bound) {
        seed = seed * 1664525 + 1013904223;
        return (seed & 0x7fffffff) % bound;
    }

    private static void require(boolean value, String message) {
        if (!value) throw new RuntimeException(message);
    }

    private static void queueState(Kernel original, Kernel list, HeapKernel heap, boolean[] present, int[] arrival) {
        require(original.sortedNode == list.sortedNode && original.sortedNode == heap.sortedNode, "Heap/list head mismatch");
        int count = 0, minimum = -1;
        for (int n = 0; n < present.length; ++n) {
            require(original.openNodePrev[n] == list.openNodePrev[n] && original.openNodeNext[n] == list.openNodeNext[n], "List links diverged");
            require((heap.openHeapPosition[n] != -1) == present[n], "Heap membership mismatch");
            if (!present[n]) continue;
            ++count;
            int p = heap.openHeapPosition[n];
            require(p >= 0 && p < heap.openHeapSize && (heap.openHeap[p] & 0xFFFF) == n, "Heap position mismatch");
            if (minimum == -1 || less(original, n, minimum, arrival)) minimum = n;
            if (p > 0) {
                int parent = heap.openHeap[(p - 1) >>> 1] & 0xFFFF;
                require(!less(original, n, parent, arrival), "Unstable or unordered heap");
            }
        }
        require(count == heap.openHeapSize && minimum == heap.sortedNode, "Heap size/minimum mismatch");
        ++queueStates;
    }

    private static boolean less(Kernel k, int a, int b, int[] arrival) {
        int af = k.nodeG[a] + k.nodeH[a], bf = k.nodeG[b] + k.nodeH[b];
        return af < bf || (af == bf && arrival[a] < arrival[b]);
    }

    private static void checkQueue() {
        Kernel original = new OriginalKernel(), list = new OptimizedKernel();
        HeapKernel heap = new HeapKernel();
        Kernel[] kernels = {original, list, heap};
        int size = 257, serial = 0;
        for (int i = 0; i < kernels.length; ++i) kernels[i].init(size, 1, new byte[size]);
        boolean[] present = new boolean[size];
        int[] arrival = new int[size];
        for (int i = 0; i < kernels.length; ++i) kernels[i].openRemove(0);
        queueState(original, list, heap, present, arrival);
        // Equal priorities must stay FIFO, including after removing/reinserting.
        for (int n = 0; n < size; ++n) {
            for (int k = 0; k < kernels.length; ++k) {
                kernels[k].nodeG[n] = 100;
                kernels[k].openAdd(n);
            }
            arrival[n] = serial++;
            present[n] = true;
            queueState(original, list, heap, present, arrival);
        }
        for (int n = 0; n < size; n += 2) {
            for (int k = 0; k < kernels.length; ++k) {
                kernels[k].openRemove(n);
                kernels[k].openAdd(n);
            }
            arrival[n] = serial++;
            queueState(original, list, heap, present, arrival);
        }
        while (original.sortedNode != -1) {
            int n = original.sortedNode;
            for (int k = 0; k < kernels.length; ++k) kernels[k].openRemove(n);
            present[n] = false;
            queueState(original, list, heap, present, arrival);
        }
        for (int step = 0; step < 20000; ++step) {
            int n = random(size);
            if (!present[n]) {
                short g = (short) (random(65536) - 32768), h = (short) (random(65536) - 32768);
                for (int k = 0; k < kernels.length; ++k) {
                    kernels[k].nodeG[n] = g;
                    kernels[k].nodeH[n] = h;
                    kernels[k].openAdd(n);
                }
                present[n] = true;
                arrival[n] = serial++;
            } else if (random(4) == 0) {
                for (int k = 0; k < kernels.length; ++k) kernels[k].openRemove(n);
                present[n] = false;
            } else {
                // A changed key must not corrupt arbitrary heap removal.
                // Short wrap-around deliberately exercises increases as well.
                short g = (short) (original.nodeG[n] - random(400));
                for (int k = 0; k < kernels.length; ++k) {
                    kernels[k].nodeG[n] = g;
                    kernels[k].openRemove(n);
                    kernels[k].openAdd(n);
                }
                arrival[n] = serial++;
            }
            queueState(original, list, heap, present, arrival);
        }
    }

    private static void pathCase(Kernel[] kernels, int[] query, int length) {
        short[][] result = new short[kernels.length][];
        boolean expected = false;
        for (int k = 0; k < kernels.length; ++k) {
            result[k] = length < 0 ? null : new short[length];
            if (result[k] != null) for (int i = 0; i < length; ++i) result[k][i] = (short) (i * 3 + 7);
            boolean found = kernels[k].pathfind(query[0], query[1], query[2], query[3], query[4], query[5] != 0, result[k]);
            if (k == 0) expected = found;
            else {
                require(found == expected, "Heap path success/failure mismatch at case " + paths);
                if (result[k] != null) for (int i = 0; i < length; ++i)
                    require(result[k][i] == result[0][i], "Heap exact path/buffer mismatch");
            }
        }
        Kernel original = kernels[0];
        for (int k = 1; k < kernels.length; ++k) {
            Kernel other = kernels[k];
            require(original.sortedNode == other.sortedNode, "Final queue head mismatch");
            for (int i = 0; i < original.nodeParent.length; ++i) {
                require(original.nodeParent[i] == other.nodeParent[i] && original.nodeG[i] == other.nodeG[i] &&
                        original.nodeH[i] == other.nodeH[i], "Heap parent/cost cleanup mismatch");
                require(original.visitedNodes[i] == other.visitedNodes[i], "Heap visited-node order mismatch");
                require(original.nodeDir[i] == other.nodeDir[i] && original.nodeX[i] == other.nodeX[i] &&
                        original.nodeY[i] == other.nodeY[i], "Heap expansion order mismatch");
            }
        }
        HeapKernel heap = (HeapKernel) kernels[2];
        require(heap.openHeapSize == 0 && heap.openHeapSerial == 0, "Heap size/serial not cleaned");
        for (int i = 0; i < heap.openHeapPosition.length; ++i) require(heap.openHeapPosition[i] == -1, "Heap position not cleaned");
        ++paths;
    }

    private static void checkPaths() throws Exception {
        int[] lengths = {-1, 0, 1, 3, 4, 9, 40, 400};
        String[] distributions = {"spread", "npc", "local"};
        for (int map = 0; map < Fixtures.MAPS.length; ++map) {
            MapData data = MapData.load(Fixtures.MAPS[map]);
            Kernel[] kernels = {new OriginalKernel(), new OptimizedKernel(), new HeapKernel()};
            for (int k = 0; k < kernels.length; ++k) kernels[k].init(data.paths.width, data.paths.height, data.paths.ground);
            int[][] spread = data.paths.queries(48);
            for (int i = 0; i < spread.length; ++i) {
                if ((i & 7) == 0) { spread[i][3] = spread[i][0]; spread[i][4] = spread[i][1]; }
                pathCase(kernels, spread[i], lengths[i % lengths.length]);
            }
            // Every timed query gets a full-buffer comparison, in addition to
            // null/truncated-buffer coverage above.
            for (int d = 0; d < distributions.length; ++d) {
                int[][] queries = data.queries(distributions[d]);
                for (int i = 0; i < queries.length; ++i) pathCase(kernels, queries[i], 1200);
            }
        }
        byte[] solid = new byte[16 * 16];
        for (int i = 0; i < solid.length; ++i) {
            if (i % 16 == 8) solid[i] = COLL_SOLID;
            else if (i % 13 == 0) solid[i] = COLL_DESK;
            else if (i % 11 == 0) solid[i] = COLL_DOOR_STAFF;
        }
        Kernel[] kernels = {new OriginalKernel(), new OptimizedKernel(), new HeapKernel()};
        for (int k = 0; k < kernels.length; ++k) kernels[k].init(16, 16, solid);
        for (int i = 0; i < 128; ++i) {
            int[] query = {random(16), random(16), random(8), random(16), random(16), i & 1};
            pathCase(kernels, query, lengths[i % lengths.length]);
        }
        System.gc();
    }

    static TileKernel[] tileKernels(MapData data, boolean shadows) {
        TileKernel[] kernels = {new OriginalTiles(), new IndexedTiles(), new CulledTiles()};
        for (int k = 0; k < kernels.length; ++k) kernels[k].init(data, shadows);
        return kernels;
    }

    private static void tileCase(TileKernel[] kernels, TraceGraphics[] graphics, int x, int y, int width, int height, int layer) {
        for (int k = 0; k < kernels.length; ++k) {
            graphics[k].reset();
            kernels[k].render(graphics[k], x, y, width, height, layer);
            require(graphics[k].color == 0, "Graphics color state changed");
            if (k > 0) {
                TraceGraphics original = graphics[0], other = graphics[k];
                require(original.size == other.size, "Visible draw-stream size mismatch at " + x + "," + y);
                for (int i = 0; i < original.size; ++i) require(original.commands[i] == other.commands[i], "Exact visible draw-stream mismatch");
                if (k == 1) require(original.rawRegions == other.rawRegions && original.rawRects == other.rawRects, "Index-only variant changed raw calls");
                else require(other.rawRegions <= original.rawRegions && other.rawRects <= original.rawRects, "Culling added calls");
            }
        }
        // The index-only variant must preserve even the wholly clipped calls.
        for (int k = 0; k < 2; ++k) {
            graphics[k].recordInvisible = true;
            graphics[k].reset();
            kernels[k].render(graphics[k], x, y, width, height, layer);
            graphics[k].recordInvisible = false;
        }
        require(graphics[0].size == graphics[1].size, "Index-only raw trace length mismatch");
        for (int i = 0; i < graphics[0].size; ++i)
            require(graphics[0].commands[i] == graphics[1].commands[i], "Index-only raw trace mismatch");
        ++tileFrames;
    }

    private static void checkTiles() throws Exception {
        int[][] screens = {{64, 64}, {176, 220}, {240, 320}, {320, 240}, {640, 480}};
        for (int map = 0; map < Fixtures.MAPS.length; ++map) {
            MapData data = MapData.load(Fixtures.MAPS[map]);
            for (int screen = 0; screen < screens.length; ++screen) {
                int width = screens[screen][0], height = screens[screen][1];
                TraceGraphics[] graphics = {new TraceGraphics(width, height), new TraceGraphics(width, height), new TraceGraphics(width, height)};
                for (int shadows = 0; shadows < 2; ++shadows) {
                    TileKernel[] kernels = tileKernels(data, shadows != 0);
                    int[][] cameras = data.cameras(width, height);
                    for (int layer = 0; layer < 4; ++layer) {
                        for (int camera = 0; camera < cameras.length; ++camera)
                            tileCase(kernels, graphics, cameras[camera][0], cameras[camera][1], width, height, layer);
                        for (int i = 0; i < 4; ++i) tileCase(kernels, graphics,
                                random(data.paths.width * TILE_SIZE + 96) - 48,
                                random(data.paths.height * TILE_SIZE + 96) - 48, width, height, layer);
                    }
                }
            }
            // Saved-game-like modifications: blank/unknown/damaged/special
            // tiles and all three shadow-neighbour combinations.
            byte[] values = {0, -1, -13, -89, 1, 13, 89, 91, 92, 95, 96, 99, 100};
            byte[] collision = {COLL_NONE, COLL_SOLID, COLL_SOLID_TRANSPARENT, COLL_DESK, COLL_DOOR_STAFF};
            for (int layer = 0; layer < 4; ++layer) for (int i = 0; i < data.tiles[layer].length; ++i) {
                data.tiles[layer][i] = values[random(values.length)];
                data.solid[layer][i] = collision[random(collision.length)];
            }
            TileKernel[] kernels = tileKernels(data, true);
            TraceGraphics[] graphics = {new TraceGraphics(240, 320), new TraceGraphics(240, 320), new TraceGraphics(240, 320)};
            for (int layer = 0; layer < 4; ++layer) for (int i = 0; i < 16; ++i)
                tileCase(kernels, graphics, random(1800) - 128, random(1700) - 128, 240, 320, layer);
            System.gc();
        }
    }
}
