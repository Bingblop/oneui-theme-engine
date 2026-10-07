package android.graphics;

import java.io.*;
import java.util.Iterator;
import javax.imageio.*;
import javax.imageio.stream.ImageInputStream;

/** Host-only ImageIO bounds stub. PNG/JPEG results do not prove Android or WebP support. */
public final class BitmapFactory {
    public static class Options {
        public boolean inJustDecodeBounds;
        public int outWidth = -1;
        public int outHeight = -1;
        public String outMimeType;
    }
    public static Bitmap decodeByteArray(byte[] input, int offset, int count, Options options) {
        options.outWidth = options.outHeight = -1;
        options.outMimeType = null;
        try (ImageInputStream stream = ImageIO.createImageInputStream(new ByteArrayInputStream(input, offset, count))) {
            Iterator<ImageReader> readers = ImageIO.getImageReaders(stream);
            if (!readers.hasNext()) return null;
            ImageReader reader = readers.next();
            try {
                reader.setInput(stream, true, true);
                options.outWidth = reader.getWidth(0);
                options.outHeight = reader.getHeight(0);
                String format = reader.getFormatName().toLowerCase(java.util.Locale.ROOT);
                options.outMimeType = "image/" + (format.equals("jpg") ? "jpeg" : format);
            } finally { reader.dispose(); }
        } catch (IOException | RuntimeException e) { return null; }
        return null;
    }
}
