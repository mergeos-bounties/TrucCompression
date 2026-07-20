/**
 * Mini encoder — interactive anatomy of the MFC1 container for small buffers.
 * Pure client-side: uses the same browser codec (mfc.js), works offline.
 */
(function () {
  "use strict";

  const MAX_BYTES = 512;
  const DEBOUNCE_MS = 250;

  const $ = (id) => document.getElementById(id);
  const input = $("miniInput");
  const summary = $("miniSummary");
  const status = $("miniStatus");
  const blocksBody = $("miniBlocks");
  const map = $("miniMap");
  const hexOut = $("miniHex");
  const blockSel = $("miniBlock");

  if (!input || !window.MFC) return;

  const textEnc = new TextEncoder();
  const textDec = new TextDecoder();

  const PRESETS = {
    zeros: { mode: "hex", make: () => new Uint8Array(96) },
    runs: {
      mode: "hex",
      make: () => {
        const out = new Uint8Array(96);
        out.fill(0xaa, 0, 40);
        out.fill(0xbb, 40, 72);
        out.fill(0xcc, 72, 96);
        return out;
      },
    },
    pattern: {
      mode: "hex",
      make: () => {
        const out = new Uint8Array(96);
        for (let i = 0; i < out.length; i++) out[i] = i % 2 ? 0x42 : 0x41;
        return out;
      },
    },
    ramp: {
      mode: "hex",
      make: () => Uint8Array.from({ length: 128 }, (_, i) => (i * 2) & 0xff),
    },
    text: {
      mode: "text",
      make: () =>
        textEnc.encode(
          "the quick brown fox jumps over the lazy dog. ".repeat(4).trimEnd(),
        ),
    },
    random: {
      mode: "hex",
      make: () => crypto.getRandomValues(new Uint8Array(96)),
    },
  };

  function currentMode() {
    const checked = document.querySelector('input[name="miniMode"]:checked');
    return checked ? checked.value : "text";
  }

  function setMode(mode) {
    const radio = document.querySelector(
      'input[name="miniMode"][value="' + mode + '"]',
    );
    if (radio) radio.checked = true;
  }

  function bytesToHexText(bytes) {
    const parts = [];
    for (let i = 0; i < bytes.length; i++) {
      parts.push(bytes[i].toString(16).padStart(2, "0"));
      if ((i + 1) % 16 === 0) parts.push("\n");
      else parts.push(" ");
    }
    return parts.join("").trimEnd();
  }

  function parseBuffer() {
    const raw = input.value;
    if (currentMode() === "text") {
      return textEnc.encode(raw);
    }
    const cleaned = raw.replace(/\s+/g, "");
    if (cleaned === "") return new Uint8Array(0);
    if (!/^[0-9a-fA-F]*$/.test(cleaned) || cleaned.length % 2 !== 0) {
      throw new Error("Hex input must be pairs of 0-9 / a-f digits");
    }
    const out = new Uint8Array(cleaned.length / 2);
    for (let i = 0; i < out.length; i++) {
      out[i] = parseInt(cleaned.slice(i * 2, i * 2 + 2), 16);
    }
    return out;
  }

  /* Walk the container and return byte regions for the map / hex dump. */
  function containerSegments(blob) {
    const segs = [
      { kind: "fh", start: 0, end: MFC.FILE_HEADER_SIZE, label: "file header" },
    ];
    const dv = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
    let offset = MFC.FILE_HEADER_SIZE;
    let index = 0;
    while (offset + MFC.BLOCK_HEADER_SIZE <= blob.length) {
      const opcode = blob[offset];
      const payloadSize = dv.getUint32(offset + 5, true);
      segs.push({
        kind: "bh",
        start: offset,
        end: offset + MFC.BLOCK_HEADER_SIZE,
        label: "block " + index + " header (" + (MFC.OP_NAMES[opcode] || opcode) + ")",
      });
      segs.push({
        kind: index % 2 ? "pl2" : "pl",
        start: offset + MFC.BLOCK_HEADER_SIZE,
        end: offset + MFC.BLOCK_HEADER_SIZE + payloadSize,
        label: "block " + index + " payload (" + payloadSize + " B)",
      });
      offset += MFC.BLOCK_HEADER_SIZE + payloadSize;
      index++;
    }
    return segs;
  }

  function renderMap(blob, segs) {
    map.textContent = "";
    const labels = [];
    for (const seg of segs) {
      const len = seg.end - seg.start;
      if (len === 0) continue;
      const div = document.createElement("div");
      div.className = "seg " + seg.kind;
      div.style.flexGrow = String(len);
      div.title = seg.label + " — bytes " + seg.start + "–" + (seg.end - 1);
      if (len / blob.length > 0.12) div.textContent = len + " B";
      map.appendChild(div);
      labels.push(seg.label + " " + len + " B");
    }
    map.setAttribute(
      "aria-label",
      "Container byte map: " + labels.join(", "),
    );
  }

  function renderHex(blob, segs) {
    hexOut.textContent = "";
    const kindAt = new Array(blob.length).fill("fh");
    for (const seg of segs) {
      for (let i = seg.start; i < seg.end && i < blob.length; i++) {
        kindAt[i] = seg.kind;
      }
    }
    const frag = document.createDocumentFragment();
    const shown = Math.min(blob.length, MAX_BYTES + 128);
    let run = null;
    for (let i = 0; i < shown; i++) {
      const txt =
        blob[i].toString(16).padStart(2, "0") +
        ((i + 1) % 16 === 0 ? "\n" : " ");
      if (run && run.kind === kindAt[i]) {
        run.node.textContent += txt;
      } else {
        const span = document.createElement("span");
        span.className = "hx-" + kindAt[i];
        span.textContent = txt;
        frag.appendChild(span);
        run = { kind: kindAt[i], node: span };
      }
    }
    if (shown < blob.length) {
      const tail = document.createElement("span");
      tail.className = "muted";
      tail.textContent = "\n… " + (blob.length - shown) + " more bytes";
      frag.appendChild(tail);
    }
    hexOut.appendChild(frag);
  }

  async function renderBlocks(data, blockSize) {
    blocksBody.textContent = "";
    if (!data.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="4" class="muted">Empty buffer — header-only container.</td>';
      blocksBody.appendChild(tr);
      return;
    }
    let previous = null;
    let index = 0;
    for (let i = 0; i < data.length; i += blockSize) {
      const block = data.subarray(i, Math.min(i + blockSize, data.length));
      const candidates = await MFC.encodeBlockCandidates(block, previous);
      let best = candidates[0];
      for (const c of candidates) {
        if (c.payload.length < best.payload.length) best = c;
      }
      const tr = document.createElement("tr");
      const cells = [
        String(index),
        block.length + " B",
        (MFC.OP_NAMES[best.opcode] || best.opcode) +
          " → " +
          best.payload.length +
          " B payload",
      ];
      for (const text of cells) {
        const td = document.createElement("td");
        td.textContent = text;
        tr.appendChild(td);
      }
      const tdCand = document.createElement("td");
      for (const c of candidates) {
        const chip = document.createElement("span");
        chip.className =
          "cand" + (c.opcode === best.opcode ? " win" : "");
        chip.textContent =
          (MFC.OP_NAMES[c.opcode] || c.opcode) +
          " " +
          (MFC.BLOCK_HEADER_SIZE + c.payload.length);
        if (c.opcode === best.opcode) {
          chip.setAttribute("aria-label", chip.textContent + " bytes, winner");
        }
        tdCand.appendChild(chip);
      }
      tr.appendChild(tdCand);
      blocksBody.appendChild(tr);
      previous = block;
      index++;
    }
  }

  let pending = 0;
  async function refresh() {
    const ticket = ++pending;
    let data;
    try {
      data = parseBuffer();
    } catch (err) {
      summary.textContent = "Input error: " + err.message;
      return;
    }
    if (data.length > MAX_BYTES) {
      summary.textContent =
        "Buffer is " + data.length + " B — the mini encoder is capped at " +
        MAX_BYTES + " B (use the playground above for big files).";
      return;
    }
    const blockSize = parseInt(blockSel.value, 10);
    status.textContent = "Encoding " + data.length + " B…";
    try {
      const { blob, report } = await MFC.compressBytes(data, blockSize);
      const { data: restored } = await MFC.decompressBytes(blob);
      if (ticket !== pending) return; // stale run superseded by newer input
      const verified = MFC.eq(restored, data);
      const ratio = data.length
        ? ((blob.length / data.length) * 100).toFixed(1) + "%"
        : "n/a";
      summary.textContent =
        data.length + " B → " + blob.length + " B container (" + ratio +
        ") · " + report.block_count + " block" +
        (report.block_count === 1 ? "" : "s") + " · SHA-256 round-trip " +
        (verified ? "verified ✓" : "FAILED ✗");
      const segs = containerSegments(blob);
      renderMap(blob, segs);
      renderHex(blob, segs);
      await renderBlocks(data, blockSize);
      status.textContent = "Every byte below is the real MFC1 container.";
    } catch (err) {
      if (ticket !== pending) return;
      summary.textContent = "Encode failed: " + err.message;
      status.textContent = "CompressionStream may be unavailable — RAW/CONST/REPEAT still work.";
    }
  }

  let timer = null;
  function scheduleRefresh() {
    clearTimeout(timer);
    timer = setTimeout(refresh, DEBOUNCE_MS);
  }

  document.querySelectorAll("[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const preset = PRESETS[btn.dataset.preset];
      if (!preset) return;
      const bytes = preset.make();
      setMode(preset.mode);
      input.value =
        preset.mode === "text" ? textDec.decode(bytes) : bytesToHexText(bytes);
      refresh();
    });
  });

  document.querySelectorAll('input[name="miniMode"]').forEach((radio) => {
    radio.addEventListener("change", refresh);
  });
  input.addEventListener("input", scheduleRefresh);
  blockSel.addEventListener("change", refresh);

  // Initial content: the text preset, encoded immediately.
  setMode("text");
  input.value = textDec.decode(PRESETS.text.make());
  refresh();
})();
