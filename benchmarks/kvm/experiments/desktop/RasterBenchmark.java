/* Separate engine: HotSpot + headless AWT software ARGB. Never labelled KVM FPS. */
public final class RasterBenchmark {
    static final class RasterTrial extends ExperimentBenchmark.TileTrial {
        RasterTrial(String scenario) throws Exception { super(scenario); }

        void prepare(int variant) throws Exception {
            graphics[variant] = new RasterGraphics(width, height, RasterGraphics.textures(data));
        }

        void run(int variant, int iterations) {
            lastVariant = variant;
            RasterGraphics g = (RasterGraphics) graphics[variant];
            TileKernel kernel = kernels[variant];
            for (int i = 0; i < iterations; ++i) {
                for (int camera = 0; camera < cameras.length; ++camera) {
                    // The game also clears its canvas before map rendering.
                    // Include this common real pixel fill, not fixture loading.
                    g.setColor(0);
                    g.fillRect(0, 0, width, height);
                    kernel.render(g, cameras[camera][0], cameras[camera][1], width, height, LAYER_GROUND);
                }
            }
        }

        int checksum() { return ((RasterGraphics) graphics[lastVariant]).pixelHash(); }
    }

    public static void main(String[] args) throws Exception {
        RasterTrial task = new RasterTrial(args[0]);
        ExperimentBenchmark.time(task, "tiles", args[0], Integer.parseInt(args[1]), Integer.parseInt(args[2]), 256);
        for (int k = 0; k < task.graphics.length; ++k) ((RasterGraphics) task.graphics[k]).close();
    }
}
