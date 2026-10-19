/* Untimed operation counts. Never substitute these kernels in timings. */
public final class ExperimentProfile {
    public static void main(String[] args) throws Exception {
        String family = args[0], scenario = args[1];
        if (family.equals("tiles")) {
            ExperimentBenchmark.TileTrial trial = new ExperimentBenchmark.TileTrial(scenario);
            int expected = 0;
            for (int variant = 0; variant < trial.names.length; ++variant) {
                trial.prepare(variant);
                trial.run(variant, 1);
                Graphics g = trial.graphics[variant];
                int checksum = trial.checksum();
                if (variant == 0) expected = checksum;
                else if (expected != checksum) throw new RuntimeException("Tile profile checksum mismatch");
                print(family, scenario, trial.names[variant], trial.units, 0, 0, 0, 0, -1,
                        g.rawRegions, g.rawRects, g.visibleRegions, g.visibleRects, checksum, 0, 0);
            }
            return;
        }
        Benchmark.Task task;
        if (family.equals("queue")) task = new Benchmark.QueueTask(scenario);
        else if (family.equals("path")) task = new ExperimentPathTask(scenario);
        else throw new RuntimeException("Unknown metric family");
        Kernel[] kernels = {new CountedOriginalKernel(), new CountedOptimizedKernel(), new CountedHeapKernel()};
        String[] names = {"original", "list", "heap"};
        int expected = 0;
        for (int i = 0; i < kernels.length; ++i) {
            task.prepare(kernels[i]);
            task.run(kernels[i], 1);
            int checksum = task.checksum();
            if (i == 0) expected = checksum;
            else if (expected != checksum) throw new RuntimeException("Frontier profile checksum mismatch");
            int adds, comparisons, removes, expanded, peak = -1;
            if (kernels[i] instanceof CountedHeapKernel) {
                CountedHeapKernel k = (CountedHeapKernel) kernels[i];
                adds = k.queueAdds; comparisons = k.heapComparisons; removes = k.queueRemoves; expanded = k.expandedNodes; peak = k.peak;
            } else {
                CountedKernel k = (CountedKernel) kernels[i];
                adds = k.queueAdds; comparisons = k.queueScanSteps; removes = k.queueRemoves; expanded = k.expandedNodes;
            }
            ExperimentPathTask path = task instanceof ExperimentPathTask ? (ExperimentPathTask) task : null;
            print(family, scenario, names[i], task.units, adds, comparisons, removes, expanded, peak,
                    0, 0, 0, 0, checksum, path == null ? 0 : path.foundQueries, path == null ? 0 : path.resultNodes);
        }
        if (task instanceof ExperimentPathTask) dumpQueries(scenario, (ExperimentPathTask) task);
    }

    private static void dumpQueries(String scenario, ExperimentPathTask task) {
        CountedHeapKernel kernel = new CountedHeapKernel();
        task.prepare(kernel);
        short[] result = new short[1200];
        for (int i = 0; i < task.queries.length; ++i) {
            int[] q = task.queries[i];
            kernel.heapComparisons = kernel.queueAdds = kernel.queueRemoves = kernel.expandedNodes = kernel.peak = 0;
            result[0] = 0;
            boolean found = kernel.pathfind(q[0], q[1], q[2], q[3], q[4], q[5] != 0, result);
            if (!scenario.endsWith(":spread") && !found) throw new RuntimeException("Reachability fixture failed");
            System.out.println("QUERY," + scenario + "," + i + "," + q[0] + "," + q[1] + "," + q[2] + "," + q[3] + "," + q[4] +
                    "," + q[5] + "," + (found ? 1 : 0) + "," + (found ? (result[0] - 1) / 2 : 0) + "," +
                    kernel.expandedNodes + "," + kernel.queueAdds + "," + kernel.heapComparisons + "," + kernel.peak);
        }
    }

    private static void print(String family, String scenario, String variant, int operations, int adds, int comparisons,
            int removes, int expanded, int peak, int rawRegions, int rawRects, int visibleRegions, int visibleRects,
            int checksum, int found, int nodes) {
        System.out.println("METRIC," + family + "," + scenario + "," + variant + "," + operations + "," + adds + "," + comparisons +
                "," + removes + "," + expanded + "," + peak + "," + rawRegions + "," + rawRects + "," + visibleRegions + "," +
                visibleRects + "," + checksum + "," + found + "," + nodes);
    }
}
