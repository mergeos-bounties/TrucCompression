/**
 * Browser port of TrucCompression MFC1 (subset of ops).
 * Compatible with Python codec for RAW/CONST/REPEAT/COPY/ZLIB/DELTA_ZLIB/XOR_ZLIB.
 * BZ2/LZMA are not used in the browser encoder (fast path).
 */
(function (global) {
  "use strict";

  const MAGIC = new TextEncoder().encode("MFC1");
  const VERSION = 1;
  const OP = {
    RAW: 0,
    CONST: 1,
    REPEAT: 2,
    COPY_PREVIOUS: 3,
    ZLIB: 4,
    BZ2: 5,
    LZMA: 6,
    DELTA_ZLIB: 7,
    XOR_ZLIB: 8,
  };
  const OP_NAMES = {
    0: "RAW",
    1: "CONST",
    2: "REPEAT",
    3: "COPY_PREVIOUS",
    4: "ZLIB",
    5: "BZ2",
    6: "LZMA",
    7: "DELTA_ZLIB",
    8: "XOR_ZLIB",
  };

  function u32le(n) {
    const b = new Uint8Array(4);
    new DataView(b.buffer).setUint32(0, n >>> 0, true);
    return b;
  }
  function u16le(n) {
    const b = new Uint8Array(2);
    new DataView(b.buffer).setUint16(0, n & 0xffff, true);
    return b;
  }
  function u64le(n) {
    const b = new Uint8Array(8);
    const v = BigInt(n);
    new DataView(b.buffer).setBigUint64(0, v, true);
    return b;
  }
  function concat(chunks) {
    let n = 0;
    for (const c of chunks) n += c.length;
    const out = new Uint8Array(n);
    let o = 0;
    for (const c of chunks) {
      out.set(c, o);
      o += c.length;
    }
    return out;
  }

  async function sha256(bytes) {
    const dig = await crypto.subtle.digest("SHA-256", bytes);
    return new Uint8Array(dig);
  }

  function hex(bytes) {
    return [...bytes].map((x) => x.toString(16).padStart(2, "0")).join("");
  }

  async function deflateZlib(bytes) {
    if (typeof CompressionStream === "undefined") {
      throw new Error("CompressionStream not supported in this browser");
    }
    const cs = new CompressionStream("deflate");
    const writer = cs.writable.getWriter();
    writer.write(bytes);
    writer.close();
    const ab = await new Response(cs.readable).arrayBuffer();
    return new Uint8Array(ab);
  }

  async function inflateZlib(bytes) {
    if (typeof DecompressionStream === "undefined") {
      throw new Error("DecompressionStream not supported in this browser");
    }
    const ds = new DecompressionStream("deflate");
    const writer = ds.writable.getWriter();
    writer.write(bytes);
    writer.close();
    const ab = await new Response(ds.readable).arrayBuffer();
    return new Uint8Array(ab);
  }

  async function gzipBytes(bytes) {
    const cs = new CompressionStream("gzip");
    const writer = cs.writable.getWriter();
    writer.write(bytes);
    writer.close();
    return new Uint8Array(await new Response(cs.readable).arrayBuffer());
  }

  async function gunzipBytes(bytes) {
    const ds = new DecompressionStream("gzip");
    const writer = ds.writable.getWriter();
    writer.write(bytes);
    writer.close();
    return new Uint8Array(await new Response(ds.readable).arrayBuffer());
  }

  function findRepeatPattern(block, maxPattern = 256) {
    const n = block.length;
    if (n < 2) return null;
    const upper = Math.min(maxPattern, Math.floor(n / 2));
    for (let p = 1; p <= upper; p++) {
      if (n % p !== 0) continue;
      let ok = true;
      for (let i = p; i < n; i++) {
        if (block[i] !== block[i % p]) {
          ok = false;
          break;
        }
      }
      if (ok) return block.slice(0, p);
    }
    return null;
  }

  function deltaEncode(block) {
    if (!block.length) return new Uint8Array(0);
    const out = new Uint8Array(block.length);
    out[0] = block[0];
    let prev = block[0];
    for (let i = 1; i < block.length; i++) {
      const cur = block[i];
      out[i] = (cur - prev) & 0xff;
      prev = cur;
    }
    return out;
  }

  function deltaDecode(enc) {
    if (!enc.length) return new Uint8Array(0);
    const out = new Uint8Array(enc.length);
    out[0] = enc[0];
    for (let i = 1; i < enc.length; i++) {
      out[i] = (out[i - 1] + enc[i]) & 0xff;
    }
    return out;
  }

  function xorEncode(block) {
    if (!block.length) return new Uint8Array(0);
    const out = new Uint8Array(block.length);
    out[0] = block[0];
    for (let i = 1; i < block.length; i++) out[i] = block[i] ^ block[i - 1];
    return out;
  }

  function xorDecode(enc) {
    if (!enc.length) return new Uint8Array(0);
    const out = new Uint8Array(enc.length);
    out[0] = enc[0];
    for (let i = 1; i < enc.length; i++) out[i] = enc[i] ^ out[i - 1];
    return out;
  }

  function eq(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }

  async function encodeBlock(block, previous) {
    const candidates = [{ opcode: OP.RAW, payload: block }];

    if (block.length && block.every((b) => b === block[0])) {
      candidates.push({ opcode: OP.CONST, payload: new Uint8Array([block[0]]) });
    }

    const pat = findRepeatPattern(block);
    if (pat) {
      candidates.push({
        opcode: OP.REPEAT,
        payload: concat([u16le(pat.length), pat]),
      });
    }

    if (previous && eq(block, previous)) {
      candidates.push({ opcode: OP.COPY_PREVIOUS, payload: new Uint8Array(0) });
    }

    try {
      candidates.push({ opcode: OP.ZLIB, payload: await deflateZlib(block) });
      candidates.push({
        opcode: OP.DELTA_ZLIB,
        payload: await deflateZlib(deltaEncode(block)),
      });
      candidates.push({
        opcode: OP.XOR_ZLIB,
        payload: await deflateZlib(xorEncode(block)),
      });
    } catch {
      /* CompressionStream missing — RAW only */
    }

    let best = candidates[0];
    let bestSize = 9 + best.payload.length;
    for (const c of candidates) {
      const s = 9 + c.payload.length;
      if (s < bestSize) {
        best = c;
        bestSize = s;
      }
    }
    return best;
  }

  async function decodeBlock(opcode, payload, originalSize, previous) {
    let out;
    if (opcode === OP.RAW) out = payload;
    else if (opcode === OP.CONST) {
      if (payload.length !== 1) throw new Error("Invalid CONST");
      out = new Uint8Array(originalSize).fill(payload[0]);
    } else if (opcode === OP.REPEAT) {
      const plen = new DataView(payload.buffer, payload.byteOffset, 2).getUint16(0, true);
      const pattern = payload.slice(2);
      if (plen !== pattern.length || !plen || originalSize % plen)
        throw new Error("Invalid REPEAT");
      out = new Uint8Array(originalSize);
      for (let i = 0; i < originalSize; i++) out[i] = pattern[i % plen];
    } else if (opcode === OP.COPY_PREVIOUS) {
      if (!previous || previous.length !== originalSize)
        throw new Error("Invalid COPY_PREVIOUS");
      out = previous;
    } else if (opcode === OP.ZLIB) out = await inflateZlib(payload);
    else if (opcode === OP.DELTA_ZLIB)
      out = deltaDecode(await inflateZlib(payload));
    else if (opcode === OP.XOR_ZLIB) out = xorDecode(await inflateZlib(payload));
    else if (opcode === OP.BZ2 || opcode === OP.LZMA)
      throw new Error("BZ2/LZMA not supported in browser player");
    else throw new Error("Unknown opcode " + opcode);

    if (out.length !== originalSize)
      throw new Error("Block size mismatch " + out.length + " != " + originalSize);
    return out instanceof Uint8Array ? out : new Uint8Array(out);
  }

  async function compressBytes(data, blockSize = 4096) {
    if (blockSize < 64 || blockSize > 16 * 1024 * 1024)
      throw new Error("block_size out of range");
    const blocks = [];
    const stats = {};
    let previous = null;
    for (let i = 0; i < data.length; i += blockSize) {
      const block = data.subarray(i, Math.min(i + blockSize, data.length));
      const cand = await encodeBlock(block, previous);
      blocks.push({ cand, originalSize: block.length });
      const name = OP_NAMES[cand.opcode] || String(cand.opcode);
      stats[name] = (stats[name] || 0) + 1;
      previous = block;
    }
    const digest = await sha256(data);
    const header = concat([
      MAGIC,
      new Uint8Array([VERSION]),
      u32le(blockSize),
      u32le(blocks.length),
      u64le(data.length),
      digest,
    ]);
    const parts = [header];
    for (const { cand, originalSize } of blocks) {
      parts.push(
        concat([
          new Uint8Array([cand.opcode]),
          u32le(originalSize),
          u32le(cand.payload.length),
          cand.payload,
        ]),
      );
    }
    const blob = concat(parts);
    return {
      blob,
      report: {
        version: VERSION,
        original_size: data.length,
        compressed_size: blob.length,
        ratio: data.length ? blob.length / data.length : 0,
        saved_percent: data.length
          ? (1 - blob.length / data.length) * 100
          : 0,
        block_size: blockSize,
        block_count: blocks.length,
        sha256: hex(digest),
        operations: stats,
      },
    };
  }

  async function decompressBytes(blob) {
    if (blob.length < 4 + 1 + 4 + 4 + 8 + 32) throw new Error("File too short");
    const dv = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
    const magic = String.fromCharCode(blob[0], blob[1], blob[2], blob[3]);
    if (magic !== "MFC1") throw new Error("Not an MFC file");
    const version = blob[4];
    if (version !== VERSION) throw new Error("Unsupported version " + version);
    const blockSize = dv.getUint32(5, true);
    const blockCount = dv.getUint32(9, true);
    // original_size is u64 little-endian at offset 13
    const originalSize = Number(dv.getBigUint64(13, true));
    const expectedHash = blob.slice(21, 53);
    let offset = 53;
    const chunksOut = [];
    let previous = null;
    const stats = {};
    for (let i = 0; i < blockCount; i++) {
      if (offset + 9 > blob.length) throw new Error("Truncated block header");
      const opcode = blob[offset];
      const rawSize = dv.getUint32(offset + 1, true);
      const payloadSize = dv.getUint32(offset + 5, true);
      offset += 9;
      if (offset + payloadSize > blob.length) throw new Error("Truncated payload");
      const payload = blob.slice(offset, offset + payloadSize);
      offset += payloadSize;
      const block = await decodeBlock(opcode, payload, rawSize, previous);
      chunksOut.push(block);
      previous = block;
      const name = OP_NAMES[opcode] || "UNKNOWN";
      stats[name] = (stats[name] || 0) + 1;
    }
    if (offset !== blob.length) throw new Error("Trailing data");
    const output = concat(chunksOut);
    if (output.length !== originalSize)
      throw new Error("Total size mismatch");
    const actual = await sha256(output);
    if (!eq(actual, expectedHash)) throw new Error("SHA-256 mismatch");
    return {
      data: output,
      report: {
        version,
        original_size: originalSize,
        compressed_size: blob.length,
        block_size: blockSize,
        block_count: blockCount,
        sha256: hex(actual),
        operations: stats,
        verified: true,
      },
    };
  }

  function humanSize(n) {
    const units = ["B", "KiB", "MiB", "GiB"];
    let v = n;
    for (const u of units) {
      if (v < 1024 || u === units[units.length - 1])
        return (u === "B" ? String(n) : v.toFixed(2)) + " " + u;
      v /= 1024;
    }
    return n + " B";
  }

  global.MFC = {
    OP,
    OP_NAMES,
    compressBytes,
    decompressBytes,
    gzipBytes,
    gunzipBytes,
    deflateZlib,
    inflateZlib,
    sha256,
    hex,
    humanSize,
    eq,
  };
})(typeof window !== "undefined" ? window : globalThis);
