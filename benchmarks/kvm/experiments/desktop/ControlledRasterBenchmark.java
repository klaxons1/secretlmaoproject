/* Confirmatory series only: same render kernels, longer intervals, all variants
 * warmed before any calibration. Java process flags are in run_awt_controlled.py.
 * Neither this nor the primary AWT series is a physical-phone measurement. */
public final class ControlledRasterBenchmark {
    private static long measure(RasterBenchmark.RasterTrial task, int variant, int iterations) {
        System.gc();
        long start = System.nanoTime();
        task.run(variant, iterations);
        return (System.nanoTime() - start) / 1000000L;
    }

    private static int calibrate(RasterBenchmark.RasterTrial task, int variant, int minimum) {
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

    public static void main(String[] args) throws Exception {
        String scenario = args[0];
        int samples = Integer.parseInt(args[1]), minimum = Integer.parseInt(args[2]);
        RasterBenchmark.RasterTrial task = new RasterBenchmark.RasterTrial(scenario);
        int[] iterations = new int[task.names.length];
        for (int variant = 0; variant < task.names.length; ++variant) task.prepare(variant);
        // Three passes through all types; avoid calibrating the first variant
        // before the JVM has even encountered the other two render methods.
        for (int warm = 0; warm < 3; ++warm)
            for (int variant = 0; variant < task.names.length; ++variant) task.run(variant, 256);
        int expected = task.checksum();
        for (int variant = 0; variant < task.names.length; ++variant) {
            iterations[variant] = calibrate(task, variant, minimum);
            if (task.checksum() != expected) throw new RuntimeException("Calibration pixels mismatch");
            System.out.println("CALIBRATE,tiles," + scenario + "," + task.names[variant] + "," + iterations[variant]);
        }
        int[][] orders = {{0, 1, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}, {1, 0, 2}, {0, 2, 1}};
        for (int sample = 0; sample < samples; ++sample) {
            for (int order = 0; order < task.names.length; ++order) {
                int variant = orders[sample % orders.length][order];
                long elapsed = measure(task, variant, iterations[variant]);
                int checksum = task.checksum();
                if (elapsed <= 0 || checksum != expected) throw new RuntimeException("Controlled raster interval/checksum mismatch");
                System.out.println("RESULT,tiles," + scenario + "," + task.names[variant] + "," + sample + "," + order + "," +
                        iterations[variant] + "," + ((long) iterations[variant] * task.units) + "," + elapsed + "," + checksum);
            }
        }
        for (int k = 0; k < task.graphics.length; ++k) ((RasterGraphics) task.graphics[k]).close();
    }
}
