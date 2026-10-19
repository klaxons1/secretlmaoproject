/* Array allocation deltas on the unchanged KVM, not desktop object-size guesses. */
public final class MemoryProbe {
    private static Kernel make(String variant) {
        if (variant.equals("original")) return new OriginalKernel();
        if (variant.equals("list")) return new OptimizedKernel();
        if (variant.equals("heap")) return new HeapKernel();
        throw new RuntimeException("Unknown variant");
    }

    public static void main(String[] args) {
        String variant = args[0];
        int width = 96, height = 93;
        byte[] ground = new byte[width * height];
        Kernel warm = make(variant);
        warm.init(width, height, ground);
        warm = null;
        System.out.println("MEMORY,variant,sample,width,height,allocated_bytes");
        Runtime runtime = Runtime.getRuntime();
        for (int sample = 0; sample < 5; ++sample) {
            Kernel kernel = make(variant); // Kernel object is excluded; arrays are measured.
            System.gc();
            long before = runtime.freeMemory();
            kernel.init(width, height, ground);
            long allocated = before - runtime.freeMemory();
            if (kernel.nodeParent.length != width * height) throw new RuntimeException("Allocation eliminated");
            System.out.println("MEMORY," + variant + "," + sample + "," + width + "," + height + "," + allocated);
        }
    }
}
