import java.io.DataInputStream;

abstract class TileKernel implements Constants {
    int width, height;
    byte[][] tiles, solid;
    Image tilesTexture, groundTexture, shadowsTexture;
    boolean enableShadows, supportsAlpha;
    TiledLayer[] tiledLayer;

    abstract void render(Graphics g, int viewX, int viewY, int viewWidth, int viewHeight, int layer);

    void init(MapData data, boolean shadows) {
        width = data.paths.width;
        height = data.paths.height;
        tiles = data.tiles;
        solid = data.solid;
        tilesTexture = data.atlas;
        groundTexture = data.ground;
        shadowsTexture = data.shadow;
        enableShadows = shadows;
        supportsAlpha = true;
    }
}

// A lightweight image descriptor for KVM command-generation tests. Real PNG
// pixels are decoded separately by the explicitly labelled desktop AWT tests.
final class Image {
    int id, width, height;
    String resource;

    static Image load(int id, String resource) throws Exception {
        Image image = new Image();
        image.id = id;
        image.resource = resource;
        DataInputStream in = new DataInputStream(image.getClass().getResourceAsStream(resource));
        if (in.readInt() != 0x89504e47 || in.readInt() != 0x0d0a1a0a) throw new RuntimeException("PNG signature");
        in.readInt();
        if (in.readInt() != 0x49484452) throw new RuntimeException("PNG IHDR");
        image.width = in.readInt();
        image.height = in.readInt();
        in.close();
        return image;
    }
}

// NOT a MIDP implementation and NOT native rendering. The timed KVM sink only
// clips/counts calls, so it measures Java command generation plus common sink
// overhead. No handset/native drawRegion or pixel-copy timing is inferred.
class Graphics {
    int clipX, clipY, clipRight, clipBottom, color;
    int rawRegions, rawRects, visibleRegions, visibleRects;

    Graphics(int width, int height) { setClip(0, 0, width, height); }

    void setClip(int x, int y, int width, int height) {
        clipX = x; clipY = y; clipRight = x + width; clipBottom = y + height;
    }

    void reset() { rawRegions = rawRects = visibleRegions = visibleRects = 0; }

    boolean visible(int x, int y, int width, int height) {
        return x < clipRight && y < clipBottom && x + width > clipX && y + height > clipY;
    }

    void setColor(int color) { this.color = color; }

    void drawRegion(Image image, int sx, int sy, int width, int height, int transform, int x, int y, int anchor) {
        ++rawRegions;
        if (visible(x, y, width, height)) ++visibleRegions;
    }

    void fillRect(int x, int y, int width, int height) {
        ++rawRects;
        if (visible(x, y, width, height)) ++visibleRects;
    }

    void fillTriangle(int x1, int y1, int x2, int y2, int x3, int y3) {
        throw new RuntimeException("NokiaUI primitive branch is outside this experiment");
    }
}

final class TraceGraphics extends Graphics {
    int[] commands = new int[32768];
    int size;
    boolean recordInvisible;

    TraceGraphics(int width, int height) { super(width, height); }

    void reset() { super.reset(); size = 0; }

    void drawRegion(Image image, int sx, int sy, int width, int height, int transform, int x, int y, int anchor) {
        if (transform != 0 || anchor != 0 || sx < 0 || sy < 0 || sx + width > image.width || sy + height > image.height)
            throw new RuntimeException("Invalid drawRegion fixture");
        super.drawRegion(image, sx, sy, width, height, transform, x, y, anchor);
        if (!recordInvisible && !visible(x, y, width, height)) return;
        add(1); add(image.id); add(sx); add(sy); add(width); add(height); add(x); add(y);
    }

    void fillRect(int x, int y, int width, int height) {
        super.fillRect(x, y, width, height);
        if (!recordInvisible && !visible(x, y, width, height)) return;
        add(2); add(color); add(x); add(y); add(width); add(height);
    }

    private void add(int value) {
        if (size >= commands.length) throw new RuntimeException("Trace capacity");
        commands[size++] = value;
    }
}

// Type-checking scaffolding for compile-time-disabled platform branches only.
// Fail rather than pretend these are real NokiaUI/TiledLayer implementations.
interface DirectGraphics { void setARGBColor(int color); }
class DirectUtils {
    static DirectGraphics getDirectGraphics(Graphics g) { throw new RuntimeException("NokiaUI not benchmarked"); }
}
class TiledLayer {
    void setPosition(int x, int y) { throw new RuntimeException("TiledLayer not benchmarked"); }
    void paint(Graphics g) { throw new RuntimeException("TiledLayer not benchmarked"); }
}
