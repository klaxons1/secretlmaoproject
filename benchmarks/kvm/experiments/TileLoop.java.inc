			// Hoist map bounds and row strides out of the per-tile path.
			// CULL_LIMITS is replaced only in the separately tested clip variant.
			int firstCol = xoff < 0 ? -xoff : 0;
			int firstRow = yoff < 0 ? -yoff : 0;
			int lastCol = viewCols;
			int lastRow = viewRows;
			// CULL_LIMITS
			if (lastCol > width - xoff) lastCol = width - xoff;
			if (lastRow > height - yoff) lastRow = height - yoff;
			byte[] tiles = this.tiles[layer];
			int rowPos = (yoff + firstRow) * width + xoff + firstCol;
			int y = firstRow * TILE_SIZE - yr;
			int mapY = yoff + firstRow;
			for (int i = firstRow; i < lastRow; ++i) {
				int x = firstCol * TILE_SIZE - xr;
				int pos = rowPos;
				int mapX = xoff + firstCol;
				for (int j = firstCol; j < lastCol; ++j) {
// TILE_BODY
					++pos;
					++mapX;
					x += TILE_SIZE;
				}
				rowPos += width;
				++mapY;
				y += TILE_SIZE;
			}
