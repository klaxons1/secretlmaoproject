import java.awt.AlphaComposite;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.awt.image.DataBufferInt;
import java.io.InputStream;
import javax.imageio.ImageIO;

/* Desktop reference renderer ONLY. This is not a phone/MIDP graphics engine. */
final class RasterGraphics extends Graphics {
    final BufferedImage canvas;
    final BufferedImage[] images;
    final Graphics2D painter;
    final int[] pixels;

    RasterGraphics(int width, int height, BufferedImage[] images) {
        super(width, height);
        this.images = images;
        canvas = new BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB);
        painter = canvas.createGraphics();
        pixels = ((DataBufferInt) canvas.getRaster().getDataBuffer()).getData();
        setClip(0, 0, width, height);
        setColor(0);
    }

    void setClip(int x, int y, int width, int height) {
        super.setClip(x, y, width, height);
        if (painter != null) painter.setClip(x, y, width, height);
    }

    void setColor(int color) {
        this.color = color;
        painter.setColor(color == 0 ? Color.BLACK : new Color(color));
    }

    void drawRegion(Image image, int sx, int sy, int width, int height, int transform, int x, int y, int anchor) {
        if (transform != 0 || anchor != 0) throw new RuntimeException("Reference renderer only supports this game's tile calls");
        painter.drawImage(images[image.id], x, y, x + width, y + height, sx, sy, sx + width, sy + height, null);
    }

    void fillRect(int x, int y, int width, int height) { painter.fillRect(x, y, width, height); }

    void clear(int color) {
        setColor(color);
        painter.setComposite(AlphaComposite.Src);
        painter.fillRect(0, 0, canvas.getWidth(), canvas.getHeight());
        painter.setComposite(AlphaComposite.SrcOver);
    }

    int pixelHash() {
        int hash = 1;
        for (int i = 0; i < pixels.length; ++i) hash = hash * 31 + pixels[i];
        return hash;
    }

    void close() { painter.dispose(); }

    static BufferedImage[] textures(MapData data) throws Exception {
        Image[] descriptors = {data.atlas, data.ground, data.shadow};
        BufferedImage[] result = new BufferedImage[descriptors.length];
        for (int i = 0; i < result.length; ++i) {
            InputStream stream = RasterGraphics.class.getResourceAsStream(descriptors[i].resource);
            BufferedImage source;
            try { source = ImageIO.read(stream); }
            finally { stream.close(); }
            if (source.getWidth() != descriptors[i].width || source.getHeight() != descriptors[i].height)
                throw new RuntimeException("PNG descriptor mismatch");
            // Explicit software ARGB surfaces, not an assumed handset format.
            result[i] = new BufferedImage(source.getWidth(), source.getHeight(), BufferedImage.TYPE_INT_ARGB);
            Graphics2D graphics = result[i].createGraphics();
            graphics.setComposite(AlphaComposite.Src);
            graphics.drawImage(source, 0, 0, null);
            graphics.dispose();
        }
        return result;
    }
}
