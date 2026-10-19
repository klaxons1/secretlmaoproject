import java.awt.image.BufferedImage;

public final class RasterChecks implements Constants {
    public static void main(String[] args) throws Exception {
        int frames = 0;
        int[][] screens = {{64, 64}, {176, 220}, {240, 320}, {320, 240}, {640, 480}};
        for (int map = 0; map < Fixtures.MAPS.length; ++map) {
            MapData data = MapData.load(Fixtures.MAPS[map]);
            BufferedImage[] textures = RasterGraphics.textures(data);
            for (int screen = 0; screen < screens.length; ++screen) {
                int width = screens[screen][0], height = screens[screen][1];
                RasterGraphics[] graphics = {new RasterGraphics(width, height, textures),
                        new RasterGraphics(width, height, textures), new RasterGraphics(width, height, textures)};
                for (int shadow = 0; shadow < 2; ++shadow) {
                    TileKernel[] kernels = ExperimentChecks.tileKernels(data, shadow != 0);
                    int[][] cameras = data.cameras(width, height);
                    for (int layer = 0; layer < 4; ++layer) {
                        for (int camera = 0; camera < cameras.length; ++camera) {
                            for (int k = 0; k < kernels.length; ++k) {
                                // Exposes transparent/blank pixels, not just opaque tile interiors.
                                graphics[k].clear(0x315975);
                                kernels[k].render(graphics[k], cameras[camera][0], cameras[camera][1], width, height, layer);
                                if (k > 0) for (int pixel = 0; pixel < graphics[k].pixels.length; ++pixel)
                                    if (graphics[k].pixels[pixel] != graphics[0].pixels[pixel])
                                        throw new RuntimeException("Reference raster mismatch: " + Fixtures.MAPS[map] + ",layer=" + layer + ",pixel=" + pixel);
                            }
                            ++frames;
                        }
                    }
                }
                for (int k = 0; k < graphics.length; ++k) graphics[k].close();
            }
        }
        System.out.println("RASTER,three-way-exact-ARGB-frames," + frames);
        System.out.println("RASTER,PASS");
    }
}
