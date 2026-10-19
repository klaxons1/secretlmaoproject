/* Test-only headless state. Production method bodies are extracted by run.py. */
abstract class Kernel implements Constants {
    int width, height;
    byte[][] solid;
    short[] nodeParent, nodeG, nodeH, openNodePrev, openNodeNext, visitedNodes;
    byte[] nodeDir, nodeX, nodeY;
    int sortedNode;

    abstract void sort(NPC[] chars);
    abstract void allocatePathfind();
    abstract boolean pathfind(int sx, int sy, int dir, int tx, int ty, boolean noStaffDoors, short[] result);
    abstract void openAdd(int node);
    abstract void openRemove(int node);

    void init(int w, int h, byte[] ground) {
        width = w;
        height = h;
        solid = new byte[][] {ground};
        allocatePathfind();
        sortedNode = -1;
    }
}

// Only fields read by the sorting kernel; no MIDP rendering or game simulation.
class NPC {
    static final int ANIM_REGULAR = 0, ANIM_STUNNED = 3, ANIM_LYING = 5;
    int id, x, y, animation;

    NPC(int id, int x, int y, int animation) {
        this.id = id;
        this.x = x;
        this.y = y;
        this.animation = animation;
    }
}

// Both versions use the same no-op logger. Console I/O is not timed.
class Profiler {
    static void log(String message) {}
}
