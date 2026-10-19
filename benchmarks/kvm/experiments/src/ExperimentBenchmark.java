/* Timed kernels are uninstrumented. Metrics live in ExperimentProfile. */
public final class ExperimentBenchmark {
    static abstract class Trial {
        int units = 1;
        String[] names;
        abstract void prepare(int variant) throws Exception;
        abstract void run(int variant, int iterations);
        abstract int checksum();
    }

    static final class KernelTrial extends Trial {
        Benchmark.Task task;
        Kernel[] kernels;

        KernelTrial(String family, String scenario) throws Exception {
            if (family.equals("sort")) {
                task = new Benchmark.SortTask(scenario);
                kernels = new Kernel[] {new OriginalKernel(), new OptimizedKernel()};
                names = new String[] {"original", "list"};
            } else {
                if (family.equals("queue")) task = new Benchmark.QueueTask(scenario);
                else if (family.equals("path")) task = new ExperimentPathTask(scenario);
                else throw new RuntimeException("Unknown benchmark family");
                kernels = new Kernel[] {new OriginalKernel(), new OptimizedKernel(), new HeapKernel()};
                names = new String[] {"original", "list", "heap"};
            }
            units = task.units;
        }

        void prepare(int variant) { task.prepare(kernels[variant]); }
        void run(int variant, int iterations) { task.run(kernels[variant], iterations); }
        int checksum() { return task.checksum(); }
    }

    static class TileTrial extends Trial implements Constants {
        MapData data;
        TileKernel[] kernels;
        Graphics[] graphics;
        int width, height;
        boolean shadows;
        int[][] cameras;
        int lastVariant;

        TileTrial(String scenario) throws Exception {
            int a = scenario.indexOf(':'), b = scenario.indexOf(':', a + 1), x = scenario.indexOf('x', a + 1);
            data = MapData.load(scenario.substring(0, a));
            width = Integer.parseInt(scenario.substring(a + 1, x));
            height = Integer.parseInt(scenario.substring(x + 1, b));
            shadows = scenario.substring(b + 1).equals("shadows");
            names = new String[] {"original", "index", "cull"};
            kernels = ExperimentChecks.tileKernels(data, shadows);
            graphics = new Graphics[names.length];
            cameras = data.cameras(width, height);
            units = cameras.length;
        }

        void prepare(int variant) throws Exception { graphics[variant] = new Graphics(width, height); }

        void run(int variant, int iterations) {
            lastVariant = variant;
            Graphics g = graphics[variant];
            TileKernel kernel = kernels[variant];
            for (int i = 0; i < iterations; ++i) {
                g.reset();
                for (int camera = 0; camera < cameras.length; ++camera)
                    kernel.render(g, cameras[camera][0], cameras[camera][1], width, height, LAYER_GROUND);
            }
        }

        int checksum() {
            Graphics g = graphics[lastVariant];
            return 31 * g.visibleRegions + g.visibleRects;
        }
    }

    private static long measure(Trial task, int variant, int iterations) {
        System.gc(); // No allocations in timed KVM kernels. Collection is untimed.
        long start = System.currentTimeMillis();
        task.run(variant, iterations);
        return System.currentTimeMillis() - start;
    }

    private static int calibrate(Trial task, int variant, int minimum) {
        int iterations = 1;
        while (true) {
            long elapsed = measure(task, variant, iterations);
            if (elapsed >= minimum) return iterations;
            int factor = elapsed == 0 ? 8 : (int) ((minimum + elapsed - 1) / elapsed);
            if (factor < 2) factor = 2;
            if (factor > 8) factor = 8;
            if (iterations > Integer.MAX_VALUE / factor) throw new RuntimeException("Calibration overflow");
            iterations *= factor;
        }
    }

    static void time(Trial task, String family, String scenario, int samples, int minimum, int warmupIterations) throws Exception {
        int[] iterations = new int[task.names.length];
        int expected = 0;
        for (int variant = 0; variant < task.names.length; ++variant) {
            task.prepare(variant);
            task.run(variant, warmupIterations);
            int actual = task.checksum();
            if (variant == 0) expected = actual;
            else if (actual != expected) throw new RuntimeException("Warm-up checksum mismatch");
            iterations[variant] = calibrate(task, variant, minimum);
            System.out.println("CALIBRATE," + family + "," + scenario + "," + task.names[variant] + "," + iterations[variant]);
        }
        // Six permutations counter systematic first/second/third-run bias.
        int[][] orders = {{0, 1, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}, {1, 0, 2}, {0, 2, 1}};
        for (int sample = 0; sample < samples; ++sample) {
            for (int order = 0; order < task.names.length; ++order) {
                int variant = task.names.length == 2 ? ((sample & 1) == 0 ? order : 1 - order) : orders[sample % orders.length][order];
                long elapsed = measure(task, variant, iterations[variant]);
                int checksum = task.checksum();
                if (elapsed <= 0 || checksum != expected) throw new RuntimeException("Measured interval/checksum mismatch");
                System.out.println("RESULT," + family + "," + scenario + "," + task.names[variant] + "," + sample + "," + order + "," +
                        iterations[variant] + "," + ((long) iterations[variant] * task.units) + "," + elapsed + "," + checksum);
            }
        }
    }

    public static void main(String[] args) throws Exception {
        String family = args[0], scenario = args[1];
        Trial task;
        if (family.equals("tiles")) task = new TileTrial(scenario);
        else task = new KernelTrial(family, scenario);
        time(task, family, scenario, Integer.parseInt(args[2]), Integer.parseInt(args[3]), 2);
    }
}

final class ExperimentPathTask extends Benchmark.Task {
    MapData data;
    int[][] queries;
    short[] result = new short[1200];
    int hash, foundQueries, resultNodes;

    ExperimentPathTask(String scenario) throws Exception {
        int colon = scenario.indexOf(':');
        data = MapData.load(scenario.substring(0, colon));
        queries = data.queries(scenario.substring(colon + 1));
        units = queries.length;
    }

    void prepare(Kernel kernel) { kernel.init(data.paths.width, data.paths.height, data.paths.ground); }

    void run(Kernel kernel, int iterations) {
        for (int i = 0; i < iterations; ++i) {
            hash = 1;
            foundQueries = resultNodes = 0;
            for (int n = 0; n < queries.length; ++n) {
                int[] q = queries[n];
                result[0] = 0;
                boolean found = kernel.pathfind(q[0], q[1], q[2], q[3], q[4], q[5] != 0, result);
                hash = 31 * hash + (found ? 1 : 0);
                if (found) {
                    ++foundQueries;
                    resultNodes += (result[0] - 1) / 2;
                    for (int p = 0; p < result[0]; ++p) hash = 31 * hash + result[p];
                }
            }
        }
    }

    int checksum() { return hash; }
}
