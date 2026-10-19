"""Source-only, reversible performance patch series; never edits production files."""
from pathlib import Path
import difflib
import os
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent.parent
sys.path.insert(0, str(PARENT))
import run as base
sys.path.insert(0, str(PARENT / "experiments"))
from run_experiments import tile_loop

MASTER = "0716b47205e297375d7a3848d923d5ce916eba6d"
PATCHES = ROOT / "patches/performance"
FILES = ("src/Game.java", "src/NPC.java", "common/src/Constants.java")


def source(revision, path):
    return subprocess.check_output(["git", "show", revision + ":" + path], cwd=ROOT).decode()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Source shape changed: " + old[:100])
    return text.replace(old, new, 1)


def change_method(text, signature, transform):
    old = base.method(text, signature)
    return once(text, old, transform(old))


def heap_base():
    result = {p: source(MASTER, p) for p in FILES}
    with tempfile.TemporaryDirectory() as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
        for args in (("read-tree", MASTER), ("apply", "--cached", str(ROOT / "patches/0003-use-stable-heap-pathfinding.patch"))):
            subprocess.run(["git", *args], cwd=ROOT, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result[FILES[0]] = subprocess.check_output(["git", "show", ":src/Game.java"], cwd=ROOT, env=env).decode()
    return result


def heuristic(state):
    def edit(body):
        start = body.index("\t\t\t\t// h cost is octile distance")
        end = body.index("\t\t\t\t// check if node is not already open", start)
        calc = body[start:end].rstrip()
        # h depends on the position/target only. Reopening never occurs.
        body = body[:start] + body[end:]
        needle = "\t\t\t\tif (openHeapPosition[n] == -1) {\n"
        return once(body, needle, needle + "\n" + "\n".join("\t" + line if line else "" for line in calc.splitlines()) + "\n\n")
    state[FILES[0]] = change_method(state[FILES[0]], "boolean pathfind(", edit)


def diagonal(state):
    def edit(body):
        start = body.index("\t\t\t\tif (i >= 4) { // check collision")
        old = base.block(body, start)
        new = ("\t\t\t\t// A diagonal must have both adjacent cardinal cells clear.\n"
               "\t\t\t\tif (i >= 4 && ((solid[nx + y * width] |\n"
               "\t\t\t\t\t\tsolid[x + ny * width]) & COLL_BIT_SOLID_AI) != 0)\n"
               "\t\t\t\t\tcontinue;")
        return once(body, old, new)
    state[FILES[0]] = change_method(state[FILES[0]], "boolean pathfind(", edit)


def stepcost(state):
    table = """	// 8 directions plus an 'other' facing, preserving arbitrary startDir values.
	private static final byte[] PATH_MOVE_COSTS = createPathMoveCosts();

	private static byte[] createPathMoveCosts() {
		byte[] costs = new byte[9 * 9 * 8];
		for (int start = 0; start < 9; ++start) {
			for (int facing = 0; facing < 9; ++facing) {
				for (int move = 0; move < 8; ++move) {
					costs[(start * 9 + facing) * 8 + move] = (byte)
							(10 + (move >= 4 ? 4 : 0) + (move != facing ? 4 : 0)
							+ (move != start ? 2 : 0));
				}
			}
		}
		return costs;
	}

"""
    state[FILES[0]] = once(state[FILES[0]], "\tshort[] nodeParent;", table + "\tshort[] nodeParent;")
    def edit(body):
        body = once(body, "\t\tint dir = startDir;", "\t\tint dir = startDir;\n\t\tbyte[] moveCosts = PATH_MOVE_COSTS;\n\t\tint startCost = (startDir >= 0 && startDir < 8 ? startDir : 8) * 72;")
        body = once(body, "\t\t\tfor (int i = 0; i < 8; ++i) { // for each direction", "\t\t\tint costOffset = startCost + ((dir >= 0 && dir < 8 ? dir : 8) << 3);\n\t\t\tfor (int i = 0; i < 8; ++i) { // for each direction")
        start = body.index("\t\t\t\t// add g cost")
        end = body.index("\n\n", body.index("if (i != startDir) g += 2;", start))
        return body[:start] + "\t\t\t\tg = gPrev + moveCosts[costOffset + i];\n\t\t\t\tif ((s & COLL_BIT_AVOID_AI) != 0) g += 15;" + body[end:]
    state[FILES[0]] = change_method(state[FILES[0]], "boolean pathfind(", edit)


def decrease(state):
    def edit(body):
        return once(body, "\t\t\t\t\topenRemove(n);\n\t\t\t\t\topenAdd(n);", "\t\t\t\t\topenImprove(n);")
    state[FILES[0]] = change_method(state[FILES[0]], "boolean pathfind(", edit)
    method = """	// Only for a strictly decreased G cost. Give reinsertions a fresh FIFO ticket.
	void openImprove(int n) {
		short[] heap = openHeap;
		short[] position = openHeapPosition;
		int[] order = openHeapOrder;
		short[] g = nodeG, h = nodeH;
		int serial = openHeapSerial++;
		order[n] = serial;
		int f = g[n] + h[n];
		int i = position[n];
		while (i > 0) {
			int parent = (i - 1) >>> 1;
			int other = heap[parent] & 0xFFFF;
			int otherF = g[other] + h[other];
			if (f > otherF || (f == otherF && serial >= order[other])) break;
			heap[i] = (short) other;
			position[other] = (short) i;
			i = parent;
		}
		heap[i] = (short) n;
		position[n] = (short) i;
		sortedNode = heap[0] & 0xFFFF;
	}

"""
    state[FILES[0]] = once(state[FILES[0]], "\t// endregion Pathfinding", method + "\t// endregion Pathfinding")


def vision(state):
    def edit(body):
        start = body.index("\t\t\tfor (int i = 1; i < n; ++i)", body.index("\t\t\tboolean found = false;"))
        old = base.block(body, start)
        new = ("\t\t\t// Passive inmates neither use 'found' nor have canSee side effects.\n"
               "\t\t\t// Guards must still scan: they can discover digged walls.\n"
               "\t\t\tif (guard || attack) {\n" +
               "\n".join("\t" + line if line else "" for line in old.splitlines()) + "\n\t\t\t}")
        return once(body, old, new)
    state[FILES[1]] = change_method(state[FILES[1]], "void tickAI(", edit)


def objects(state):
    def edit(body):
        old = """				short sprite = objects[idx + 2];
				int w = (sprite & (3 << 8)) >> 8, h = (sprite & (3 << 10)) >> 10;
				if ((x == ox && y == oy)
						// check dimensions of non-single tile objects
						|| (x >= ox && x < ox + w && y > oy - h && y <= oy)) {
					return idx;
				}"""
        new = """				// Reject outside the anchor's left/bottom half-planes before decoding.
				if (x < ox || y > oy) continue;
				// Anchor hits must work even for zero-sized/disabled sprites.
				if (x == ox && y == oy) return idx;
				short sprite = objects[idx + 2];
				int w = (sprite & (3 << 8)) >> 8, h = (sprite & (3 << 10)) >> 10;
				if (x < ox + w && y > oy - h) return idx;"""
        return once(body, old, new)
    state[FILES[0]] = change_method(state[FILES[0]], "int getObjectIdxAt(", edit)


def zones(state):
    text = state[FILES[0]]
    fields = "\n\tprivate int[] indexedZones;\n\tprivate short[] firstZoneByType, nextZoneOfType;\n"
    text = once(text, "\tint[] zones; // int[5] {count, [x,y,x1,x2,type], ...}", "\tint[] zones; // int[5] {count, [x,y,x1,x2,type], ...}" + fields)
    helper = """	// Zone data is immutable after load; a new map replaces the zones array.
	private void ensureZoneIndex() {
		if (indexedZones == zones) return;
		short[] first = new short[ZONE_SAFE + 1];
		short[] next = new short[zones[0]];
		for (int i = 0; i < first.length; ++i) first[i] = -1;
		for (int i = next.length - 1; i >= 0; --i) {
			int type = zones[i * 5 + 5];
			next[i] = -1;
			if (type >= 0 && type < first.length) {
				next[i] = first[type];
				first[type] = (short) i;
			}
		}
		firstZoneByType = first;
		nextZoneOfType = next;
		indexedZones = zones;
	}

"""
    text = once(text, "\tboolean isInZone(int x, int y, int zone) {", helper + "\tboolean isInZone(int x, int y, int zone) {")
    code = """		if (zone >= 0 && zone <= ZONE_SAFE) {
			ensureZoneIndex();
			int[] zones = this.zones;
			for (int i = firstZoneByType[zone]; i != -1; i = nextZoneOfType[i]) {
				int idx = i * 5 + 1;
				if (x >= zones[idx] && x <= zones[idx + 2] &&
						y >= zones[idx + 1] && y <= zones[idx + 3]) return true;
			}
			return false;
		}
"""
    text = once(text, "\tboolean isInZone(int x, int y, int zone) {\n", "\tboolean isInZone(int x, int y, int zone) {\n" + code)
    text = once(text, "\tint findZone(int zone) {\n", "\tint findZone(int zone) {\n\t\tif (zone >= 0 && zone <= ZONE_SAFE) {\n\t\t\tensureZoneIndex();\n\t\t\tint i = firstZoneByType[zone];\n\t\t\treturn i == -1 ? -1 : i * 5 + 1;\n\t\t}\n")
    state[FILES[0]] = text


def zone_memo(state):
    text = state[FILES[1]]
    fields = "\t// Membership bits belong to one exact position and one immutable zone array.\n\tprivate int zoneCacheX, zoneCacheY, zoneCacheChecked, zoneCacheFound;\n\tprivate int[] zoneCacheData;\n\n"
    text = once(text, "\tboolean isInZone(int zone) {", fields + "\tboolean isInZone(int zone) {")
    new = """boolean isInZone(int zone) {
		int px = x + 7, py = y + 7;
		if (zone < 0 || zone > ZONE_SAFE) return map.isInZone(px, py, zone);
		if (zoneCacheData != map.zones || zoneCacheX != px || zoneCacheY != py) {
			zoneCacheData = map.zones;
			zoneCacheX = px;
			zoneCacheY = py;
			zoneCacheChecked = zoneCacheFound = 0;
		}
		int bit = 1 << zone;
		if ((zoneCacheChecked & bit) == 0) {
			if (map.isInZone(px, py, zone)) zoneCacheFound |= bit;
			zoneCacheChecked |= bit;
		}
		return (zoneCacheFound & bit) != 0;
	}"""
    state[FILES[1]] = change_method(text, "boolean isInZone(", lambda _: new)


def seats(state):
    def edit(body):
        body = once(body, "\t\tint n = positions[0];", "\t\tint n = positions[0];\n\t\tif (((x | y) & ~0xFF) != 0) return -1;\n\t\tint packed = x | (y << 8);")
        return once(body, "(pos & 0xFF) == x && (pos >> 8 & 0xFF) == y", "(pos & 0xFFFF) == packed")
    state[FILES[0]] = change_method(state[FILES[0]], "int getSeatIndex(", edit)


def facing(state):
    def edit(body):
        start = body.index("\t\tfloat distance =")
        end = body.index("\n\n\t\tthis.x =", start)
        old = body[start:end]
        # Keep NaN/Inf and squared-distance underflow on the old path. Preserve
        # signed-zero products as well, without changing nonzero-speed math.
        fallback = once(old, "Math.sqrt(dx * dx + dy * dy)", "Math.sqrt(distanceSquared)")
        guard = ("\t\tfloat distanceSquared = dx * dx + dy * dy;\n"
                 "\t\tif (speed == 0f && distanceSquared > 0f\n"
                 "\t\t\t\t&& distanceSquared < Float.POSITIVE_INFINITY) {\n"
                 "\t\t\t// Turning only: the normalized vector times zero is signed zero.\n"
                 "\t\t\txFloat += dx < 0f ? -speed : speed;\n"
                 "\t\t\tyFloat += dy < 0f ? -speed : speed;\n\t\t} else {\n" +
                 "\n".join("\t" + line if line else "" for line in fallback.splitlines()) + "\n\t\t}")
        return once(body, old, guard)
    state[FILES[1]] = change_method(state[FILES[1]], "void moveTowards(", edit)


def tile_index(state):
    text = tile_loop(state[FILES[0]], False)
    # Transplanted old blank lines carry tabs; do not introduce whitespace errors.
    state[FILES[0]] = change_method(text, "void paintMap(", lambda body: "\n".join(line.rstrip() for line in body.splitlines()))


def tile_cull(state):
    def edit(body):
        # This is also applicable without row-stride optimization. All callers
        # clip to the viewport; do not change the NokiaUI triangle branch.
        needle = "\t\t\tint xoff = viewx / TILE_SIZE, yoff = viewy / TILE_SIZE;"
        body = once(body, needle, needle + "\n\n\t\t\tif (!NOKIAUI_SHADOWS) {\n\t\t\t\tint cols = (viewWidth + xr + TILE_SIZE - 1) / TILE_SIZE;\n\t\t\t\tint rows = (viewHeight + yr + TILE_SIZE - 1) / TILE_SIZE;\n\t\t\t\tif (viewCols > cols) viewCols = cols;\n\t\t\t\tif (viewRows > rows) viewRows = rows;\n\t\t\t}")
        body = once(body, "int y0 = viewHeight / (TILE_SIZE * 3) + 1;", "int y0 = (viewHeight + yr + TILE_SIZE * 3 - 1) / (TILE_SIZE * 3) - 1;")
        return once(body, "for (int x = viewWidth / (TILE_SIZE * 3) + 1; x >= 0; --x)", "for (int x = (viewWidth + xr + TILE_SIZE * 3 - 1) / (TILE_SIZE * 3) - 1; x >= 0; --x)")
    state[FILES[0]] = change_method(state[FILES[0]], "void paintMap(", edit)


def release(state):
    state[FILES[2]] = once(state[FILES[2]], "static final boolean LOGGING = true;", "// Release-only: re-enable for diagnostics; avoids console I/O and debug strings.\n\tstatic final boolean LOGGING = false;")


def diagnostic(state):
    text = state[FILES[0]]
    text = once(text, "\tint lag;", "\tint lag;\n\tint npcPathCalls, npcPathFails, npcPathExpanded;\n\tlong npcPathTime;\n\tint npcPeakAI, npcPeakTick, npcPeakPathCalls, npcPeakPathFails, npcPeakExpanded, npcPeakPathMs;")
    text = once(text, "\t\tlong l = System.currentTimeMillis();\n\n\t\tNPC[] chars", "\t\tnpcPathCalls = npcPathFails = npcPathExpanded = 0;\n\t\tnpcPathTime = 0;\n\t\tlong aiTime = 0, tickTime = 0;\n\t\tlong l = System.currentTimeMillis();\n\n\t\tNPC[] chars")
    text = once(text, "\t\t\tif (i != 0) chars[i].tickAI(tick);\n\t\t\tchars[i].tick();", "\t\t\tlong t = System.currentTimeMillis();\n\t\t\tif (i != 0) chars[i].tickAI(tick);\n\t\t\tlong afterAI = System.currentTimeMillis();\n\t\t\taiTime += afterAI - t;\n\t\t\tchars[i].tick();\n\t\t\ttickTime += System.currentTimeMillis() - afterAI;")
    text = once(text, "\t\tif (l > lag) lag = (int) l;", "\t\tif (l >= lag) {\n\t\t\tlag = (int) l;\n\t\t\tnpcPeakAI = (int) aiTime;\n\t\t\tnpcPeakTick = (int) tickTime;\n\t\t\tnpcPeakPathCalls = npcPathCalls;\n\t\t\tnpcPeakPathFails = npcPathFails;\n\t\t\tnpcPeakExpanded = npcPathExpanded;\n\t\t\tnpcPeakPathMs = (int) npcPathTime;\n\t\t}")
    def edit(body):
        body = once(body, "\t\tint width = this.width;", "\t\tlong profileStart = System.currentTimeMillis();\n\t\tnpcPathCalls++;\n\t\tint width = this.width;")
        body = once(body, "\t\twhile (cur != -1) {\n\t\t\topenRemove(cur);", "\t\twhile (cur != -1) {\n\t\t\tnpcPathExpanded++;\n\t\t\topenRemove(cur);")
        return once(body, "\t\treturn ret;", "\t\tnpcPathTime += System.currentTimeMillis() - profileStart;\n\t\tif (!ret) npcPathFails++;\n\t\treturn ret;")
    text = change_method(text, "boolean pathfind(", edit)
    needle = "\t\t\t\t// used heap"
    hud = """				// Peak-NPC-pass breakdown (same pass, not independent maxima).
				// y=71: AI ms / pathfind ms / remaining tick ms.
				drawNumber(g, npcPeakAI, fontImg, 0, 16, 5, 7, 0, 71);
				drawNumber(g, npcPeakPathMs, fontImg, 0, 16, 5, 7, 40, 71);
				drawNumber(g, npcPeakTick, fontImg, 0, 16, 5, 7, 80, 71);
				// y=79: path calls / failed calls (includes short buffers) / expansions.
				drawNumber(g, npcPeakPathCalls, fontImg, 0, 16, 5, 7, 0, 79);
				drawNumber(g, npcPeakPathFails, fontImg, 0, 16, 5, 7, 40, 79);
				drawNumber(g, npcPeakExpanded, fontImg, 0, 16, 5, 7, 80, 79);

"""
    text = once(text, needle, hud + needle)
    text = once(text, "\t\t\t\t\tlag = 0;", "\t\t\t\t\tlag = 0;\n\t\t\t\t\tnpcPeakAI = npcPeakTick = npcPeakPathCalls = npcPeakPathFails = npcPeakExpanded = npcPeakPathMs = 0;")
    state[FILES[0]] = text


# Separate files, separate commits. Cumulative series starts AFTER 0003.
SPECS = [
    ("0004", "discovery-heuristic", "heuristic", heuristic),
    ("0005", "diagonal-collision", "diagonal", diagonal),
    ("0006", "movement-cost-table", "stepcost", stepcost),
    ("0007", "heap-decrease-key", "decrease", decrease),
    ("0008", "passive-inmate-vision", "vision", vision),
    ("0009", "object-broad-phase", "objects", objects),
    ("0010", "zone-type-index", "zones", zones),
    ("0011", "npc-zone-memo", "memo", zone_memo),
    ("0012", "packed-seat-lookup", "seats", seats),
    ("0013", "facing-only-movement", "facing", facing),
    ("0014", "tile-row-strides", "tile-index", tile_index),
    ("0015", "clip-invisible-tiles", "tile-cull", tile_cull),
    ("0016", "release-logging-off", "release", release),
]
DIAGNOSTIC = ("0017", "npc-lag-breakdown", "diagnostic", diagnostic)
CORE_COUNT = 10


def variants():
    baseline = heap_base()
    result = {"heap": baseline}
    for number, label, name, transform in SPECS + [DIAGNOSTIC]:
        state = dict(baseline)
        transform(state)
        result[name] = state
    state = dict(baseline)
    for _, _, _, transform in SPECS[:CORE_COUNT]: transform(state)
    result["core"] = dict(state)
    for _, _, _, transform in SPECS[CORE_COUNT:]: transform(state)
    result["all"] = dict(state)
    return result


def diff(before, after, title, prerequisites, context=3):
    result = title + "\nBase-master: " + MASTER + "\nPrerequisites: " + prerequisites + "\nApply with git apply, NOT git am.\n\n"
    for path in FILES:
        if before[path] == after[path]: continue
        result += "diff --git a/" + path + " b/" + path + "\n"
        result += "".join(difflib.unified_diff(before[path].splitlines(True), after[path].splitlines(True), fromfile="a/" + path, tofile="b/" + path, n=context))
    return result


def export():
    PATCHES.mkdir(parents=True, exist_ok=True)
    (PATCHES / "standalone").mkdir(exist_ok=True)
    state = heap_base()
    baseline = dict(state)
    files = []
    for number, label, name, transform in SPECS:
        previous = dict(state)
        transform(state)
        filename = number + "-" + label + ".patch"
        (PATCHES / filename).write_text(diff(previous, state, label, "0003 and preceding numbered performance patches"))
        single = dict(baseline); transform(single)
        (PATCHES / "standalone" / filename).write_text(diff(baseline, single, label, "0003 ONLY; do not combine with the cumulative copy of this patch"))
        files.append(filename)
    (PATCHES / "series.txt").write_text("\n".join(files) + "\n")
    (PATCHES / "all-after-heap.patch").write_text(diff(baseline, state, "Combined 0004-0016 (not the diagnostic)", "0003 ONLY; alternative to applying the series, not in addition"))
    original = {p: source(MASTER, p) for p in FILES}
    (PATCHES / "all-from-master.patch").write_text(diff(original, state, "Combined heap and 0004-0016 (not the diagnostic)", "master " + MASTER + " ONLY; no patches already applied"))
    number, label, name, transform = DIAGNOSTIC
    diagnostics = dict(baseline); transform(diagnostics)
    (PATCHES / (number + "-" + label + ".patch")).write_text(diff(baseline, diagnostics, "Diagnostic only: overhead makes these numbers unsuitable for performance A/B", "0003; apply separately or AFTER optimizations; NOT part of series.txt", context=1))
    return files


if __name__ == "__main__":
    for name in export(): print(name)
