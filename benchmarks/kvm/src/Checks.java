final class Checks implements Constants {
    private static int seed = 0x13579bdf;
    private static int sortCases, queueSteps, pathCases;

    public static void main(String[] args) throws Exception {
        checkSort();
        checkQueue();
        checkPaths();
        System.out.println("CHECKS,sort," + sortCases);
        System.out.println("CHECKS,queue," + queueSteps);
        System.out.println("CHECKS,path," + pathCases);
        System.out.println("CHECKS,PASS");
    }

    private static int random(int bound) {
        seed = seed * 1664525 + 1013904223;
        return (seed & 0x7fffffff) % bound;
    }

    private static void require(boolean value, String message) {
        if (!value) throw new RuntimeException(message);
    }

    private static void sortCase(Kernel original, Kernel optimized, NPC[] input) {
        NPC[] a = new NPC[input.length], b = new NPC[input.length];
        System.arraycopy(input, 0, a, 0, a.length);
        System.arraycopy(input, 0, b, 0, b.length);
        original.sort(a);
        optimized.sort(b);
        for (int i = 0; i < a.length; ++i) {
            require(a[i] == b[i], "Sort identity/stability mismatch");
            require((input[i] == null) == (b[i] == null), "Null barrier moved");
        }
        ++sortCases;
    }

    private static void checkSort() throws Exception {
        Kernel a = new OriginalKernel(), b = new OptimizedKernel();
        // Every sequence of length 0..7 over null and four keys/animations.
        // Distinct objects at equal keys make stability observable.
        int combinations = 1;
        for (int length = 0; length <= 7; ++length) {
            NPC[] input = new NPC[length];
            NPC[][] pool = new NPC[length][4];
            for (int i = 0; i < length; ++i) {
                pool[i][0] = new NPC(i, 0, -1, NPC.ANIM_REGULAR);
                pool[i][1] = new NPC(i, 0, 0, NPC.ANIM_REGULAR);
                pool[i][2] = new NPC(i, 0, 10001, NPC.ANIM_STUNNED);
                pool[i][3] = new NPC(i, 0, 10000, NPC.ANIM_LYING);
            }
            for (int pattern = 0; pattern < combinations; ++pattern) {
                int value = pattern;
                for (int i = 0; i < length; ++i) {
                    int symbol = value % 5;
                    value /= 5;
                    input[i] = symbol == 0 ? null : pool[i][symbol - 1];
                }
                sortCase(a, b, input);
            }
            combinations *= 5;
        }
        for (int trial = 0; trial < 4000; ++trial) {
            NPC[] input = new NPC[random(97)];
            for (int i = 0; i < input.length; ++i) {
                if (random(5) == 0) continue;
                if (i > 0 && random(16) == 0) {
                    input[i] = input[random(i)]; // repeated reference, possibly null
                    continue;
                }
                int y = random(4096) - 2048;
                if ((trial & 7) == 0) y = random(2) == 0 ? Integer.MIN_VALUE : Integer.MAX_VALUE;
                input[i] = new NPC(i, 0, y, random(10) - 1);
            }
            sortCase(a, b, input);
        }
        for (int i = 0; i < Fixtures.MAPS.length; ++i) {
            Fixtures fixture = Fixtures.load(Fixtures.MAPS[i]);
            sortCase(a, b, fixture.chars);
            System.out.println("MAP," + fixture.name + "," + fixture.width + "," + fixture.height +
                    "," + fixture.chars.length + "," + fixture.active);
        }
        String[] maps = {"perks", "irongate", "shanktonstatepen"};
        String[] layouts = {"spawn", "sorted", "near", "reverse"};
        for (int map = 0; map < maps.length; ++map) {
            for (int layout = 0; layout < layouts.length; ++layout) {
                Benchmark.SortTask task = new Benchmark.SortTask(maps[map] + ":" + layouts[layout]);
                int inversions = 0;
                for (int i = 0; i < task.source.length; ++i) {
                    NPC left = task.source[i];
                    if (left == null) continue;
                    int key = left.y - ((left.animation == NPC.ANIM_STUNNED || left.animation == NPC.ANIM_LYING) ? 10000 : 0);
                    for (int j = i + 1; j < task.source.length && task.source[j] != null; ++j) {
                        NPC right = task.source[j];
                        int other = right.y - ((right.animation == NPC.ANIM_STUNNED || right.animation == NPC.ANIM_LYING) ? 10000 : 0);
                        if (key > other) ++inversions;
                    }
                }
                if (layouts[layout].equals("sorted")) require(inversions == 0, "Sorted fixture not sorted");
                if (layouts[layout].equals("near")) require(inversions == 3, "Near fixture must have exactly three inversions");
                sortCase(a, b, task.source);
            }
        }
    }

    private static void arrays(short[] a, short[] b, String message) {
        require(a.length == b.length, message);
        for (int i = 0; i < a.length; ++i) require(a[i] == b[i], message);
    }

    private static void queueState(Kernel a, Kernel b, boolean[] present) {
        require(a.sortedNode == b.sortedNode, "Queue head mismatch");
        arrays(a.openNodePrev, b.openNodePrev, "Queue prev mismatch");
        arrays(a.openNodeNext, b.openNodeNext, "Queue next mismatch");
        int previous = -1, node = a.sortedNode, count = 0;
        while (node != -1) {
            require(++count <= present.length, "Queue cycle");
            require(present[node], "Unexpected queue member");
            require(a.openNodePrev[node] == previous, "Broken back-link");
            if (previous != -1) require(a.nodeG[previous] + a.nodeH[previous] <=
                    a.nodeG[node] + a.nodeH[node], "Queue costs out of order");
            previous = node;
            node = a.openNodeNext[node];
        }
        int expected = 0;
        for (int i = 0; i < present.length; ++i) if (present[i]) ++expected;
        require(count == expected, "Queue lost a node");
        ++queueSteps;
    }

    private static void checkQueue() {
        Kernel a = new OriginalKernel(), b = new OptimizedKernel();
        int size = 257;
        a.init(size, 1, new byte[size]);
        b.init(size, 1, new byte[size]);
        boolean[] present = new boolean[size];
        a.openRemove(0); // pathfind also removes its not-enqueued start node
        b.openRemove(0);
        queueState(a, b, present);
        for (int i = 0; i < size; ++i) {
            a.nodeG[i] = b.nodeG[i] = 100;
            a.openAdd(i);
            b.openAdd(i);
            present[i] = true;
            queueState(a, b, present);
        }
        for (int i = 0; i < size; ++i) {
            require(a.sortedNode == i && b.sortedNode == i, "Equal-cost FIFO changed");
            a.openRemove(i);
            b.openRemove(i);
            present[i] = false;
            queueState(a, b, present);
        }
        for (int step = 0; step < 10000; ++step) {
            int node = random(size);
            if (!present[node]) {
                a.nodeG[node] = b.nodeG[node] = (short) random(2000);
                a.nodeH[node] = b.nodeH[node] = (short) random(1200);
                a.openAdd(node);
                b.openAdd(node);
                present[node] = true;
            } else if (random(3) == 0) {
                a.openRemove(node);
                b.openRemove(node);
                present[node] = false;
            } else {
                // Decrease-key, followed by the game's remove/reinsert sequence.
                a.nodeG[node] = b.nodeG[node] = (short) (a.nodeG[node] - random(20));
                a.openRemove(node);
                b.openRemove(node);
                a.openAdd(node);
                b.openAdd(node);
            }
            queueState(a, b, present);
        }
        // Signed short costs and endpoint insertion/removal.
        for (int i = 0; i < size; ++i) {
            if (present[i]) {
                a.openRemove(i);
                b.openRemove(i);
            }
            present[i] = false;
        }
        for (int i = 0; i < size; ++i) {
            a.nodeG[i] = b.nodeG[i] = (short) (i * 1000);
            a.nodeH[i] = b.nodeH[i] = (short) (i * 777);
            a.openAdd(i);
            b.openAdd(i);
            present[i] = true;
            queueState(a, b, present);
        }
    }

    private static void pathCase(Kernel a, Kernel b, int[] query, int length) {
        short[] x = length < 0 ? null : new short[length];
        short[] y = length < 0 ? null : new short[length];
        if (x != null) {
            for (int i = 0; i < length; ++i) x[i] = y[i] = (short) (i * 3 + 7);
        }
        boolean original = a.pathfind(query[0], query[1], query[2], query[3], query[4], query[5] != 0, x);
        boolean optimized = b.pathfind(query[0], query[1], query[2], query[3], query[4], query[5] != 0, y);
        require(original == optimized, "Path success/failure mismatch");
        if (x != null) arrays(x, y, "Exact path/buffer mismatch");
        arrays(a.nodeParent, b.nodeParent, "Parent cleanup mismatch");
        arrays(a.nodeG, b.nodeG, "G cleanup mismatch");
        arrays(a.nodeH, b.nodeH, "H cleanup mismatch");
        arrays(a.openNodePrev, b.openNodePrev, "Prev cleanup mismatch");
        arrays(a.openNodeNext, b.openNodeNext, "Next cleanup mismatch");
        arrays(a.visitedNodes, b.visitedNodes, "Visited order mismatch");
        require(a.sortedNode == b.sortedNode, "Path queue head mismatch");
        for (int i = 0; i < a.nodeDir.length; ++i) {
            require(a.nodeDir[i] == b.nodeDir[i] && a.nodeX[i] == b.nodeX[i] &&
                    a.nodeY[i] == b.nodeY[i], "Path expansion order mismatch");
            require(a.nodeParent[i] == -1 && a.nodeG[i] == 0 && a.nodeH[i] == 0 &&
                    a.openNodePrev[i] == -1 && a.openNodeNext[i] == -1, "Dirty path workspace");
        }
        ++pathCases;
    }

    private static void checkPaths() throws Exception {
        int[] lengths = {-1, 0, 1, 3, 4, 9, 40, 400};
        for (int map = 0; map < Fixtures.MAPS.length; ++map) {
            Fixtures f = Fixtures.load(Fixtures.MAPS[map]);
            Kernel a = new OriginalKernel(), b = new OptimizedKernel();
            a.init(f.width, f.height, f.ground);
            b.init(f.width, f.height, f.ground);
            int[][] queries = f.queries(48);
            for (int i = 0; i < queries.length; ++i) {
                if ((i & 7) == 0) { // start == target
                    queries[i][3] = queries[i][0];
                    queries[i][4] = queries[i][1];
                }
                pathCase(a, b, queries[i], lengths[i % lengths.length]);
            }
        }
        // Synthetic geometry explicitly exercises disconnected regions, avoid
        // costs, diagonal corner blocking, and staff-door policy.
        byte[] ground = new byte[16 * 16];
        for (int i = 0; i < ground.length; ++i) {
            if (i % 16 == 8) ground[i] = COLL_SOLID;
            else if (i % 13 == 0) ground[i] = COLL_DESK;
            else if (i % 11 == 0) ground[i] = COLL_DOOR_STAFF;
        }
        Kernel a = new OriginalKernel(), b = new OptimizedKernel();
        a.init(16, 16, ground);
        b.init(16, 16, ground);
        for (int i = 0; i < 128; ++i) {
            int[] query = {random(16), random(16), random(8), random(16), random(16), i & 1};
            pathCase(a, b, query, lengths[i % lengths.length]);
        }
    }
}
