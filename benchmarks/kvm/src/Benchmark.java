/* All timing happens inside the pinned original KVM, not desktop HotSpot. */
public final class Benchmark {
    static abstract class Task {
        int units = 1;
        abstract void prepare(Kernel kernel);
        abstract void run(Kernel kernel, int iterations);
        abstract int checksum();
    }

    static final class SortTask extends Task {
        NPC[] source, work;

        SortTask(String scenario) throws Exception {
            int colon = scenario.indexOf(':');
            Fixtures f = Fixtures.load(scenario.substring(0, colon));
            String layout = scenario.substring(colon + 1);
            source = f.chars;
            work = new NPC[source.length];
            if (!layout.equals("spawn")) {
                new OriginalKernel().sort(source); // untimed fixture preparation
                if (layout.equals("near")) {
                    // Three disjoint adjacent inversions, skipping equal keys.
                    // Swapping ties would only change identity, not sortedness.
                    int swaps = 0;
                    for (int p = 0; p < f.active - 1 && swaps < 3; ++p) {
                        NPC left = source[p], right = source[p + 1];
                        int leftKey = left.y - ((left.animation == NPC.ANIM_STUNNED || left.animation == NPC.ANIM_LYING) ? 10000 : 0);
                        int rightKey = right.y - ((right.animation == NPC.ANIM_STUNNED || right.animation == NPC.ANIM_LYING) ? 10000 : 0);
                        if (leftKey == rightKey) continue;
                        source[p] = right;
                        source[p + 1] = left;
                        ++swaps;
                        ++p;
                    }
                    if (swaps != 3) throw new RuntimeException("Not enough unequal adjacent keys");
                } else if (layout.equals("reverse")) {
                    for (int i = 0; i < f.active / 2; ++i) {
                        NPC t = source[i];
                        source[i] = source[f.active - 1 - i];
                        source[f.active - 1 - i] = t;
                    }
                } else if (!layout.equals("sorted")) {
                    throw new RuntimeException("Unknown sort layout");
                }
            }
            System.out.println("FIXTURE,sort," + scenario + ",slots=" + source.length + ",active=" + f.active);
        }

        void prepare(Kernel kernel) {}

        void run(Kernel kernel, int iterations) {
            for (int i = 0; i < iterations; ++i) {
                System.arraycopy(source, 0, work, 0, source.length);
                kernel.sort(work);
            }
        }

        int checksum() {
            int hash = 1;
            for (int i = 0; i < work.length; ++i) hash = 31 * hash + (work[i] == null ? 0 : work[i].id + 1);
            return hash;
        }
    }

    static final class QueueTask extends Task {
        int size;
        String layout;
        int[] order;

        QueueTask(String scenario) {
            int colon = scenario.indexOf(':');
            layout = scenario.substring(0, colon);
            size = Integer.parseInt(scenario.substring(colon + 1));
            order = new int[size];
        }

        void prepare(Kernel kernel) {
            kernel.init(size, 1, new byte[size]);
            for (int i = 0; i < size; ++i) {
                if (layout.equals("head")) kernel.nodeG[i] = (short) (size - i);
                else if (layout.equals("ties")) kernel.nodeG[i] = 100;
                else if (layout.equals("mixed")) kernel.nodeG[i] = (short) ((i * 137) % 251);
                else throw new RuntimeException("Unknown queue layout");
            }
        }

        void run(Kernel kernel, int iterations) {
            for (int i = 0; i < iterations; ++i) {
                kernel.sortedNode = -1;
                for (int n = 0; n < size; ++n) kernel.openAdd(n);
                for (int n = 0; n < size; ++n) {
                    int node = kernel.sortedNode;
                    order[n] = node;
                    kernel.openRemove(node);
                }
            }
        }

        int checksum() {
            int hash = 1;
            for (int i = 0; i < order.length; ++i) hash = 31 * hash + order[i];
            return hash;
        }
    }

    static final class PathTask extends Task {
        Fixtures fixture;
        int[][] queries;
        short[] result = new short[400];
        int hash;

        PathTask(String scenario) throws Exception {
            fixture = Fixtures.load(scenario);
            queries = fixture.queries(8);
            units = queries.length;
        }

        void prepare(Kernel kernel) {
            kernel.init(fixture.width, fixture.height, fixture.ground);
        }

        void run(Kernel kernel, int iterations) {
            for (int i = 0; i < iterations; ++i) {
                hash = 1;
                for (int n = 0; n < queries.length; ++n) {
                    int[] q = queries[n];
                    result[0] = 0;
                    boolean found = kernel.pathfind(q[0], q[1], q[2], q[3], q[4], q[5] != 0, result);
                    hash = 31 * hash + (found ? 1 : 0);
                    if (found) {
                        for (int p = 0; p < result[0]; ++p) hash = 31 * hash + result[p];
                    }
                }
            }
        }

        int checksum() { return hash; }
    }

    private static long measure(Task task, Kernel kernel, int iterations) {
        System.gc(); // outside the interval; timed kernels allocate nothing
        long start = System.currentTimeMillis();
        task.run(kernel, iterations);
        return System.currentTimeMillis() - start;
    }

    private static int calibrate(Task task, Kernel kernel, int minimum) {
        int iterations = 1;
        while (true) {
            long elapsed = measure(task, kernel, iterations);
            if (elapsed >= minimum) return iterations;
            int factor = elapsed == 0 ? 8 : (int) ((minimum + elapsed - 1) / elapsed);
            if (factor < 2) factor = 2;
            if (factor > 8) factor = 8;
            if (iterations > Integer.MAX_VALUE / factor) throw new RuntimeException("Calibration overflow");
            iterations *= factor;
        }
    }

    public static void main(String[] args) throws Exception {
        String family = args[0], scenario = args[1];
        int samples = Integer.parseInt(args[2]), minimum = Integer.parseInt(args[3]);
        Task task;
        if (family.equals("sort")) task = new SortTask(scenario);
        else if (family.equals("queue")) task = new QueueTask(scenario);
        else if (family.equals("path")) task = new PathTask(scenario);
        else throw new RuntimeException("Unknown benchmark family");
        Kernel[] kernels = {new OriginalKernel(), new OptimizedKernel()};
        int[] iterations = new int[2];
        int expected = 0;
        for (int variant = 0; variant < kernels.length; ++variant) {
            task.prepare(kernels[variant]);
            task.run(kernels[variant], 2); // untimed warm-up batches
            int actual = task.checksum();
            if (variant == 0) expected = actual;
            else if (actual != expected) throw new RuntimeException("Warm-up checksum mismatch");
            iterations[variant] = calibrate(task, kernels[variant], minimum);
            System.out.println("CALIBRATE," + family + "," + scenario + "," + variant + "," + iterations[variant]);
        }
        for (int sample = 0; sample < samples; ++sample) {
            // AB/BA paired order counters systematic first/second-run bias.
            for (int order = 0; order < 2; ++order) {
                int variant = (sample & 1) == 0 ? order : 1 - order;
                long elapsed = measure(task, kernels[variant], iterations[variant]);
                int checksum = task.checksum(); // outside interval except common path result hashing
                if (checksum != expected) throw new RuntimeException("Measured checksum mismatch");
                System.out.println("RESULT," + family + "," + scenario + "," +
                        (variant == 0 ? "original" : "optimized") + "," + sample + "," + order + "," +
                        iterations[variant] + "," + ((long) iterations[variant] * task.units) + "," + elapsed + "," + checksum);
            }
        }
    }
}
