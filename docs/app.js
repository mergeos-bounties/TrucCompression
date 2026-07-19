/**
 * TrucCompression Pages playground — compress, restore, compare codecs.
 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = {
    bytes: null,
    name: "",
    kind: "binary",
    mfcBlob: null,
    restored: null,
  };

  function log(msg, cls) {
    const el = $("log");
    const line = document.createElement("div");
    if (cls) line.className = cls;
    line.textContent = msg;
    el.prepend(line);
  }

  function setStatus(t) {
    $("status").textContent = t;
  }

  function human(n) {
    return MFC.humanSize(n);
  }

  function download(bytes, filename, mime) {
    const blob = new Blob([bytes], { type: mime || "application/octet-stream" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  async function loadArrayBuffer(ab, name, kind) {
    state.bytes = new Uint8Array(ab);
    state.name = name;
    state.kind = kind || "binary";
    state.mfcBlob = null;
    state.restored = null;
    $("fileMeta").textContent =
      name + " · " + human(state.bytes.length) + " · " + state.bytes.length + " bytes";
    $("btnCompress").disabled = false;
    $("btnRestore").disabled = true;
    $("btnDownloadMfc").disabled = true;
    $("btnDownloadRestored").disabled = true;
    setStatus("Loaded " + name);
    await runCompare();
  }

  async function fetchSample(path, name, kind) {
    setStatus("Loading sample…");
    try {
      const res = await fetch(path);
      if (!res.ok) throw new Error(res.status + " " + path);
      await loadArrayBuffer(await res.arrayBuffer(), name, kind);
      log("Sample loaded: " + name, "ok");
    } catch (e) {
      log("Fetch failed (" + e.message + ") — generating sample in-browser", "warn");
      await loadGenerated(name);
    }
  }

  async function loadGenerated(which) {
    let bytes;
    let kind = "binary";
    if (which === "zeros") bytes = new Uint8Array(4096);
    else if (which === "const") bytes = new Uint8Array(2048).fill(0x51);
    else if (which === "repeat") {
      bytes = new Uint8Array(2048);
      for (let i = 0; i < bytes.length; i++) bytes[i] = i % 2 ? 0x42 : 0x41;
    } else if (which === "text") {
      const s = "hello world ";
      const enc = new TextEncoder().encode(s.repeat(256));
      bytes = enc;
    } else if (which === "ramp") {
      bytes = new Uint8Array(256 * 8);
      for (let i = 0; i < bytes.length; i++) bytes[i] = i % 256;
    } else if (which === "noise") {
      bytes = crypto.getRandomValues(new Uint8Array(4096));
    } else if (which === "tone") {
      // PCM 16-bit mono tone as raw (not full WAV) for fair lossless compare
      const sr = 8000,
        n = 4000;
      bytes = new Uint8Array(n * 2);
      const dv = new DataView(bytes.buffer);
      for (let i = 0; i < n; i++) {
        const v = Math.sin((2 * Math.PI * 440 * i) / sr) * 16000;
        dv.setInt16(i * 2, v | 0, true);
      }
      kind = "audio-pcm";
    } else if (which === "image-raw") {
      // Synthetic 64x64 RGB ramp (raw)
      const w = 64,
        h = 64;
      bytes = new Uint8Array(w * h * 3);
      let o = 0;
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          bytes[o++] = (x * 4) & 255;
          bytes[o++] = (y * 4) & 255;
          bytes[o++] = ((x + y) * 2) & 255;
        }
      kind = "image-raw";
    } else {
      bytes = new Uint8Array(1024).fill(7);
    }
    await loadArrayBuffer(bytes.buffer, which + " (generated)", kind);
  }

  function renderTable(rows) {
    const tb = $("cmpBody");
    tb.innerHTML = "";
    for (const r of rows) {
      const tr = document.createElement("tr");
      if (r.best) tr.classList.add("best");
      tr.innerHTML =
        "<td>" +
        r.method +
        "</td><td>" +
        r.size +
        "</td><td>" +
        r.ratio +
        "</td><td>" +
        r.saved +
        "</td><td>" +
        r.time +
        "</td><td>" +
        r.verify +
        "</td><td class='muted'>" +
        (r.notes || "") +
        "</td>";
      tb.appendChild(tr);
    }
  }

  async function timeIt(fn) {
    const t0 = performance.now();
    const result = await fn();
    return { result, ms: performance.now() - t0 };
  }

  async function runCompare() {
    if (!state.bytes) return;
    const data = state.bytes;
    const blockSize = Number($("blockSize").value) || 4096;
    $("blockSizeVal").textContent = String(blockSize);
    setStatus("Compressing / comparing…");
    const rows = [];

    rows.push({
      method: "Original",
      size: human(data.length),
      sizeBytes: data.length,
      ratio: "100%",
      saved: "0%",
      time: "—",
      verify: "—",
      notes: state.kind,
    });

    // MFC
    try {
      const { result, ms } = await timeIt(() =>
        MFC.compressBytes(data, blockSize),
      );
      const { blob, report } = result;
      state.mfcBlob = blob;
      const dec = await MFC.decompressBytes(blob);
      state.restored = dec.data;
      const ok = MFC.eq(dec.data, data);
      const ops = Object.entries(report.operations)
        .map(([k, v]) => k + ":" + v)
        .join(", ");
      rows.push({
        method: "MFC1 (TrucCompression)",
        size: human(blob.length),
        sizeBytes: blob.length,
        ratio: (report.ratio * 100).toFixed(2) + "%",
        saved: report.saved_percent.toFixed(2) + "%",
        time: ms.toFixed(1) + " ms",
        verify: ok ? "OK" : "FAIL",
        notes: ops,
      });
      $("btnRestore").disabled = false;
      $("btnDownloadMfc").disabled = false;
      $("btnDownloadRestored").disabled = false;
      $("opsOut").textContent = JSON.stringify(report, null, 2);
    } catch (e) {
      rows.push({
        method: "MFC1 (TrucCompression)",
        size: "—",
        ratio: "—",
        saved: "—",
        time: "—",
        verify: "ERR",
        notes: String(e.message || e),
      });
      log("MFC error: " + e.message, "err");
    }

    // Gzip
    try {
      const { result: gz, ms } = await timeIt(() => MFC.gzipBytes(data));
      const { result: back, ms: ms2 } = await timeIt(() => MFC.gunzipBytes(gz));
      const ok = MFC.eq(back, data);
      rows.push({
        method: "Gzip (browser CompressionStream)",
        size: human(gz.length),
        sizeBytes: gz.length,
        ratio: ((gz.length / Math.max(1, data.length)) * 100).toFixed(2) + "%",
        saved: ((1 - gz.length / Math.max(1, data.length)) * 100).toFixed(2) + "%",
        time: ms.toFixed(1) + " + " + ms2.toFixed(1) + " ms",
        verify: ok ? "OK" : "FAIL",
        notes: "media-friendly whole-stream",
      });
    } catch (e) {
      rows.push({
        method: "Gzip",
        size: "—",
        ratio: "—",
        saved: "—",
        time: "—",
        verify: "N/A",
        notes: e.message || String(e),
      });
    }

    // Deflate / zlib
    try {
      const { result: df, ms } = await timeIt(() => MFC.deflateZlib(data));
      const { result: back } = await timeIt(() => MFC.inflateZlib(df));
      const ok = MFC.eq(back, data);
      rows.push({
        method: "Deflate/zlib (browser)",
        size: human(df.length),
        sizeBytes: df.length,
        ratio: ((df.length / Math.max(1, data.length)) * 100).toFixed(2) + "%",
        saved: ((1 - df.length / Math.max(1, data.length)) * 100).toFixed(2) + "%",
        time: ms.toFixed(1) + " ms",
        verify: ok ? "OK" : "FAIL",
        notes: "same family as Python zlib",
      });
    } catch (e) {
      rows.push({
        method: "Deflate/zlib",
        size: "—",
        ratio: "—",
        saved: "—",
        time: "—",
        verify: "N/A",
        notes: e.message || String(e),
      });
    }

    // Media notes
    if (state.kind === "image-file" || state.name.match(/\.(png|jpe?g|webp|gif)$/i)) {
      rows.push({
        method: "Media container (as uploaded)",
        size: human(data.length),
        ratio: "100%",
        saved: "0%",
        time: "—",
        verify: "—",
        notes:
          "Already entropy-coded (PNG/JPEG/WebP). MFC rarely beats the container — compare raw pixels via “Image raw RGB” sample.",
      });
    }
    if (state.kind === "audio-file" || state.name.match(/\.wav$/i)) {
      rows.push({
        method: "WAV container",
        size: human(data.length),
        ratio: "100%",
        saved: "0%",
        time: "—",
        verify: "—",
        notes: "Header + PCM. MFC often wins on silence/tone; MP3/AAC are lossy and not comparable 1:1.",
      });
    }

    // Mark smallest compressed among codecs that have numeric sizeBytes
    let bestI = -1;
    let bestS = Infinity;
    rows.forEach((r, i) => {
      if (r.sizeBytes == null || r.method === "Original") return;
      if (r.sizeBytes < bestS) {
        bestS = r.sizeBytes;
        bestI = i;
      }
      r.best = false;
    });
    if (bestI >= 0) rows[bestI].best = true;
    renderTable(rows);
    setStatus("Compare done for " + state.name);
  }

  async function onFile(file) {
    const ab = await file.arrayBuffer();
    let kind = "binary";
    if (/\.(png|jpe?g|webp|gif)$/i.test(file.name)) kind = "image-file";
    else if (/\.(wav|flac|mp3|ogg)$/i.test(file.name)) kind = "audio-file";
    else if (/\.(mp4|webm|mov)$/i.test(file.name)) kind = "video-file";
    await loadArrayBuffer(ab, file.name, kind);

    // If image, also offer raw RGBA extract size in log
    if (kind === "image-file") {
      try {
        const bmp = await createImageBitmap(file);
        const canvas = document.createElement("canvas");
        canvas.width = bmp.width;
        canvas.height = bmp.height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(bmp, 0, 0);
        const img = ctx.getImageData(0, 0, bmp.width, bmp.height);
        const raw = img.data; // RGBA
        log(
          "Decoded pixels RGBA: " +
            bmp.width +
            "×" +
            bmp.height +
            " = " +
            human(raw.byteLength) +
            " raw (container was " +
            human(ab.byteLength) +
            "). Use “Compare raw pixels” to run MFC on raw.",
          "ok",
        );
        $("btnRawPixels").disabled = false;
        $("btnRawPixels").onclick = async () => {
          await loadArrayBuffer(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength), file.name + " (RGBA raw)", "image-raw");
        };
      } catch (e) {
        log("Could not decode image pixels: " + e.message, "warn");
      }
    }
  }

  function wire() {
    $("blockSize").addEventListener("input", () => {
      $("blockSizeVal").textContent = $("blockSize").value;
    });

    document.querySelectorAll("[data-sample]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-sample");
        const map = {
          zeros: ["samples/zeros.bin", "zeros.bin", "binary"],
          const: ["samples/const.bin", "const.bin", "binary"],
          repeat: ["samples/repeat.bin", "repeat.bin", "binary"],
          text: ["samples/text.bin", "text.bin", "binary"],
          ramp: ["samples/ramp.bin", "ramp.bin", "binary"],
          noise: ["samples/noise_4k.bin", "noise_4k.bin", "binary"],
          tone: ["samples/tone_440.wav", "tone_440.wav", "audio-file"],
          png: ["samples/gradient_32.png", "gradient_32.png", "image-file"],
          "image-raw": [null, "image-raw", "image-raw"],
          "tone-pcm": [null, "tone", "audio-pcm"],
        };
        const m = map[id];
        if (!m) return;
        if (!m[0]) loadGenerated(m[1]);
        else fetchSample(m[0], m[1], m[2]);
      });
    });

    $("fileInput").addEventListener("change", (e) => {
      const f = e.target.files && e.target.files[0];
      if (f) onFile(f);
    });

    const drop = $("drop");
    drop.addEventListener("dragover", (e) => {
      e.preventDefault();
      drop.classList.add("drag");
    });
    drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("drag");
      const f = e.dataTransfer.files[0];
      if (f) onFile(f);
    });

    $("btnCompress").addEventListener("click", () => runCompare());
    $("btnRestore").addEventListener("click", async () => {
      if (!state.mfcBlob) return;
      try {
        const { data, report } = await MFC.decompressBytes(state.mfcBlob);
        state.restored = data;
        const ok = state.bytes && MFC.eq(data, state.bytes);
        log(
          "Restored " +
            human(data.length) +
            " · SHA-256 " +
            report.sha256.slice(0, 16) +
            "… · " +
            (ok ? "matches original" : "differs"),
          ok ? "ok" : "err",
        );
        $("btnDownloadRestored").disabled = false;
      } catch (e) {
        log("Restore error: " + e.message, "err");
      }
    });
    $("btnDownloadMfc").addEventListener("click", () => {
      if (state.mfcBlob)
        download(state.mfcBlob, (state.name || "out").replace(/\.[^.]+$/, "") + ".mfc");
    });
    $("btnDownloadRestored").addEventListener("click", () => {
      if (state.restored)
        download(state.restored, "restored_" + (state.name || "data.bin"));
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    wire();
    // Auto-load zeros sample
    fetchSample("samples/zeros.bin", "zeros.bin", "binary");
  });
})();
