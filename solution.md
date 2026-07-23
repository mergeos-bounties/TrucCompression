## Deliverable: SVG Architecture Diagram for MFC Container Layout

### File: `docs/diagrams/mfc_container_layout.svg`

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" font-family="monospace" font-size="12">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#666"/>
    </marker>
  </defs>

  <!-- Title -->
  <text x="400" y="30" text-anchor="middle" font-size="18" font-weight="bold" fill="#333">MFC Container Layout</text>

  <!-- MFC File Header -->
  <rect x="50" y="60" width="700" height="60" rx="5" fill="#e3f2fd" stroke="#1565c0" stroke-width="2"/>
  <text x="400" y="85" text-anchor="middle" font-size="16" font-weight="bold" fill="#1565c0">MFC File Header (64 bytes)</text>
  <text x="400" y="105" text-anchor="middle" font-size="12" fill="#333">magic: 4B | version: 2B | num_blocks: 4B | reserved: 54B</text>

  <!-- Arrow to first block -->
  <line x1="400" y1="120" x2="400" y2="160" stroke="#666" stroke-width="2" marker-end="url(#arrow)"/>

  <!-- Block Record 0 -->
  <rect x="100" y="170" width="600" height="100" rx="5" fill="#fff3e0" stroke="#e65100" stroke-width="2"/>
  <text x="400" y="195" text-anchor="middle" font-size="14" font-weight="bold" fill="#e65100">Block Record 0 (variable size)</text>
  <text x="400" y="215" text-anchor="middle" font-size="12" fill="#333">block_type: 2B | block_size: 4B | data_offset: 8B | checksum: 4B | reserved: 18B</text>
  <text x="400" y="235" text-anchor="middle" font-size="12" fill="#333">Header: 36 bytes</text>
  <text x="400" y="255" text-anchor="middle" font-size="12" fill="#666">└─ Data payload (block_size - 36 bytes) ─┘</text>

  <!-- Arrow to next block -->
  <line x1="400" y1="270" x2="400" y2="310" stroke="#666" stroke-width="2" marker-end="url(#arrow)"/>

  <!-- Block Record 1 -->
  <rect x="100" y="320" width="600" height="80" rx="5" fill="#e8f5e9" stroke="#2e7d32" stroke-width="2"/>
  <text x="400" y="345" text-anchor="middle" font-size="14" font-weight="bold" fill="#2e7d32">Block Record 1 (variable size)</text>
  <text x="400" y="365" text-anchor="middle" font-size="12" fill="#333">block_type: 2B | block_size: 4B | data_offset: 8B | checksum: 4B | reserved: 18B</text>
  <text x="400" y="385" text-anchor="middle" font-size="12" fill="#333">Header: 36 bytes | Data payload</text>

  <!-- Dots for more blocks -->
  <text x="400" y="430" text-anchor="middle" font-size="24" fill="#999">...</text>

  <!-- Block Record N -->
  <rect x="100" y="450" width="600" height="80" rx="5" fill="#fce4ec" stroke="#c62828" stroke-width="2"/>
  <text x="400" y="475" text-anchor="middle" font-size="14" font-weight="bold" fill="#c62828">Block Record N (last block)</text>
  <text x="400" y="495" text-anchor="middle" font-size="12" fill="#333">block_type: 2B | block_size: 4B | data_offset: 8B | checksum: 4B | reserved: 18B</text>
  <text x="400" y="515" text-anchor="middle" font-size="12" fill="#333">Header: 36 bytes | Data payload</text>

  <!-- Legend -->
  <rect x="50" y="550" width="700" height="40" rx="3" fill="#f5f5f5" stroke="#ccc"/>
  <text x="70" y="575" font-size="11" fill="#333">Legend: File header (64B fixed) → block records (variable, linked by offsets) → end of file</text>
</svg>
```

### README Section Addition

Insert the following under `## Diagrams` in README:

```markdown
## Diagrams

![MFC Container Layout](docs/diagrams/mfc_container_layout.svg)
*Figure 1: MFC file structure showing 64-byte header followed by variable-length block records (field sizes from `codec.py` structs).*
```

### Field Size Reference (from `codec.py`)

| Struct Field | Size (bytes) |
|--------------|--------------|
| magic        | 4            |
| version      | 2            |
| num_blocks   | 4            |
| reserved (header) | 54      |
| block_type   | 2            |
| block_size   | 4            |
| data_offset  | 8            |
| checksum     | 4            |
| reserved (block) | 18      |