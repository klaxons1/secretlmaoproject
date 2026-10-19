import java.util.Random;

/* Headless state only. Candidate method bodies are extracted from full sources.
 * No MIDP implementation, whole-game emulation, or claimed PSP timing here. */
abstract class PerfGame extends Kernel {
    short[] openHeap, openHeapPosition;
    int[] openHeapOrder;
    int openHeapSize, openHeapSerial;
    short[][] objects;
    int[] zones, indexedZones;
    short[] firstZoneByType, nextZoneOfType;
    int note, solitaryReason, fightFreq;
    Actor[] chars;
    static StringBuffer stringBuffer = new StringBuffer();
    int expanded, heuristics, adds, removes, improves, peak;

    void sort(NPC[] chars) {}
    void openImprove(int n) { openRemove(n); openAdd(n); }
    abstract int getObjectIdxAt(int x, int y, int layer);
    abstract int findObject(int obj, int layer, int start);
    abstract int getSeatIndex(short[] positions, int x, int y);
    abstract boolean isInZone(int x, int y, int zone);
    abstract int findZone(int zone);

    void load(WorldData world) {
        width = world.width;
        height = world.height;
        solid = world.maps.solid;
        objects = world.objects;
        zones = world.zones;
        fightFreq = world.fightFreq;
    }

    void resetCounts() { expanded = heuristics = adds = removes = improves = peak = 0; }
}

abstract class Actor implements Constants {
    static final int ANIM_REGULAR = 0, ANIM_STUNNED = 3, ANIM_LYING = 5;
    static final int DIR_RIGHT = 0, DIR_UP = 1, DIR_LEFT = 2, DIR_DOWN = 3;
    static final int AI_RESET = -1, AI_IDLE = 0, AI_CHECK = 1, AI_ROAM = 2,
        AI_ATTACK = 3, AI_WAYPOINT = 4, AI_SLEEP = 5;
    static Random rng = new Random(1);
    PerfGame map;
    int id, x, y, direction, layer, health = 15, fighting;
    int animation, aiState, aiWaitTimer, angerTimer;
    boolean guard, inmate, inCabinet, targetReached, correctPath;
    float xFloat = -1, yFloat = -1;
    String name;
    Actor chaseTarget;
    int heatCalls, heatHash, lastHeatAmount;
    String lastHeatText;
    int zoneCacheX, zoneCacheY, zoneCacheChecked, zoneCacheFound;
    int[] zoneCacheData;

    abstract void moveTowards(int tx, int ty, float speed);
    abstract boolean isInZone(int zone);
    abstract boolean canSee(Actor other);
    abstract boolean canSee(int tx, int ty);
    abstract void visionCandidates();

    // Record all observable heat-call arguments/state in this extracted block.
    // This is NOT a substitute for full combat/gameplay integration testing.
    void heat(String text, int amount) {
        ++heatCalls;
        lastHeatText = text; lastHeatAmount = amount;
        heatHash = 31 * heatHash + text.hashCode() + amount;
    }
}
