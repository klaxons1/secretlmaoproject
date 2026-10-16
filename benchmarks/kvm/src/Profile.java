/* Operation counts are collected separately, NEVER from timed classes. */
public final class Profile {
    public static void main(String[] args) throws Exception {
        String family = args[0], scenario = args[1];
        Benchmark.Task task;
        if (family.equals("sort")) task = new Benchmark.SortTask(scenario);
        else if (family.equals("queue")) task = new Benchmark.QueueTask(scenario);
        else if (family.equals("path")) task = new Benchmark.PathTask(scenario);
        else throw new RuntimeException("Unknown profile family");
        CountedKernel[] kernels = {new CountedOriginalKernel(), new CountedOptimizedKernel()};
        int expected = 0;
        for (int i = 0; i < kernels.length; ++i) {
            CountedKernel k = kernels[i];
            task.prepare(k);
            task.run(k, 1);
            int checksum = task.checksum();
            if (i == 0) expected = checksum;
            else if (expected != checksum) throw new RuntimeException("Profile checksum mismatch");
            System.out.println("METRIC," + family + "," + scenario + "," + (i == 0 ? "original" : "optimized") +
                    "," + task.units + "," + k.sortAdjacentTests + "," + k.sortKeyComparisons + "," +
                    k.queueAdds + "," + k.queueScanSteps + "," + k.queueRemoves + "," + k.expandedNodes + "," + checksum);
        }
    }
}

abstract class CountedKernel extends Kernel {
    int sortAdjacentTests, sortKeyComparisons, queueAdds, queueScanSteps, queueRemoves, expandedNodes;

    boolean countSortComparison() {
        ++sortKeyComparisons;
        return true;
    }

    boolean scan(int f, int other) {
        ++queueScanSteps;
        return f >= other;
    }
}
