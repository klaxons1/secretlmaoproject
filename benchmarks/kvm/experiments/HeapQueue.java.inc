	// Stable binary min-heap. Extra storage versus the two list arrays: one
	// int per map cell for FIFO tie-breaking. No search-time allocations.
	short[] openHeap;
	short[] openHeapPosition;
	int[] openHeapOrder;
	int openHeapSize, openHeapSerial;

	void openAdd(int n) {
		short[] heap = openHeap;
		short[] position = openHeapPosition;
		int[] order = openHeapOrder;
		short[] g = nodeG, h = nodeH;
		if (openHeapSize == 0) openHeapSerial = 0;
		int serial = openHeapSerial++;
		order[n] = serial;
		int f = g[n] + h[n];
		int i = openHeapSize++;
		// HEAP_PEAK
		while (i > 0) {
			int parent = (i - 1) >>> 1;
			int other = heap[parent] & 0xFFFF;
			int otherF = g[other] + h[other];
			// HEAP_COMPARE
			if (f > otherF || (f == otherF && serial >= order[other])) break;
			heap[i] = (short) other;
			position[other] = (short) i;
			i = parent;
		}
		heap[i] = (short) n;
		position[n] = (short) i;
		sortedNode = heap[0] & 0xFFFF;
	}

	void openRemove(int n) {
		short[] heap = openHeap;
		short[] position = openHeapPosition;
		int i = position[n];
		// The initial start node is expanded without first being enqueued.
		if (i == -1) return;
		position[n] = -1;
		int size = --openHeapSize;
		if (i < size) {
			int moved = heap[size] & 0xFFFF;
			int[] order = openHeapOrder;
			short[] g = nodeG, h = nodeH;
			int f = g[moved] + h[moved];
			int serial = order[moved];
			int hole = i;
			// Removing an arbitrary item can require either sift direction.
			// This also handles decrease-key: pathfind updates nodeG[n]
			// BEFORE removing n, then reinserts it with a fresh FIFO serial.
			while (i > 0) {
				int parent = (i - 1) >>> 1;
				int other = heap[parent] & 0xFFFF;
				int otherF = g[other] + h[other];
				// HEAP_COMPARE
				if (f > otherF || (f == otherF && serial >= order[other])) break;
				heap[i] = (short) other;
				position[other] = (short) i;
				i = parent;
			}
			if (i == hole) {
				int child = (i << 1) + 1;
				while (child < size) {
					int other = heap[child] & 0xFFFF;
					int otherF = g[other] + h[other];
					if (child + 1 < size) {
						int right = heap[child + 1] & 0xFFFF;
						int rightF = g[right] + h[right];
						// HEAP_COMPARE
						if (rightF < otherF || (rightF == otherF && order[right] < order[other])) {
							++child;
							other = right;
							otherF = rightF;
						}
					}
					// HEAP_COMPARE
					if (f < otherF || (f == otherF && serial <= order[other])) break;
					heap[i] = (short) other;
					position[other] = (short) i;
					i = child;
					child = (i << 1) + 1;
				}
			}
			heap[i] = (short) moved;
			position[moved] = (short) i;
		}
		sortedNode = size == 0 ? -1 : heap[0] & 0xFFFF;
	}
