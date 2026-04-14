const imagesInput = document.getElementById("imagesInput");
const modeSelect = document.getElementById("modeSelect");
const compressToSelect = document.getElementById("compressToSelect");
const targetSelect = document.getElementById("targetSelect");
const targetSizeInput = document.getElementById("targetSizeInput");
const runBtn = document.getElementById("runBtn");
const downloadBtn = document.getElementById("downloadBtn");
const statusText = document.getElementById("statusText");
const progressBar = document.getElementById("progressBar");
const resultBody = document.getElementById("resultBody");
const summaryText = document.getElementById("summaryText");
const compressToWrap = document.getElementById("compressToWrap");
const targetWrap = document.getElementById("targetWrap");
const dropZone = document.getElementById("dropZone");
const pickFilesBtn = document.getElementById("pickFilesBtn");
const fileMeta = document.getElementById("fileMeta");
const presetSelect = document.getElementById("presetSelect");
const clearAllBtn = document.getElementById("clearAllBtn");
const resultFilter = document.getElementById("resultFilter");
const retryFailedBtn = document.getElementById("retryFailedBtn");
const exportCsvBtn = document.getElementById("exportCsvBtn");
const historyText = document.getElementById("historyText");
const historyList = document.getElementById("historyList");
const previewGrid = document.getElementById("previewGrid");
const previewMore = document.getElementById("previewMore");
const sumCount = document.getElementById("sumCount");
const sumBefore = document.getElementById("sumBefore");
const sumAfter = document.getElementById("sumAfter");
const sumRatio = document.getElementById("sumRatio");

const STORAGE_STATE = "imgTool.frontend.state";
const STORAGE_HISTORY = "imgTool.frontend.history";

/** 固定版本，避免 CDN 静默升级破坏兼容；首次编码时会下载 WASM（约数百 KB）。 */
const JSQUASH_WEBP_ENCODE = "https://cdn.jsdelivr.net/npm/@jsquash/webp@1.3.0/encode.js";
const JSQUASH_JPEG_ENCODE = "https://cdn.jsdelivr.net/npm/@jsquash/jpeg@1.2.0/encode.js";

const MIME_BY_EXT = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
};

let outputFiles = [];
let selectedFiles = [];
let latestRows = [];
let failedNames = [];
let latestSourceFiles = [];
const historyItems = [];

function bytesToKb(bytes) {
  return `${(Number(bytes || 0) / 1024).toFixed(1)} KB`;
}

function extOf(filename) {
  const parts = filename.toLowerCase().split(".");
  return parts.length > 1 ? parts.pop() : "";
}

function mimeFromExt(ext) {
  return MIME_BY_EXT[ext] || null;
}

function setProgress(value) {
  const v = Math.max(0, Math.min(100, value));
  progressBar.style.width = `${v}%`;
}

function isAllowedFile(file) {
  const ext = extOf(file.name || "");
  return ["png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"].includes(ext);
}

function updateFileMeta() {
  if (!selectedFiles.length) {
    fileMeta.textContent = "未选择文件";
    previewGrid.innerHTML = "";
    previewMore.textContent = "";
    return;
  }
  const total = selectedFiles.reduce((sum, f) => sum + (f.size || 0), 0);
  fileMeta.textContent = `已选择 ${selectedFiles.length} 个文件，约 ${(total / 1024 / 1024).toFixed(2)} MB`;
  renderSelectedPreview();
}

function setSelectedFiles(files) {
  selectedFiles = files.filter(isAllowedFile);
  updateFileMeta();
  refreshPreview();
}

function renderSelectedPreview() {
  const maxPreview = 16;
  previewGrid.innerHTML = "";
  const show = selectedFiles.slice(0, maxPreview);
  for (let i = 0; i < show.length; i += 1) {
    const file = show[i];
    const card = document.createElement("div");
    card.className = "preview-item";
    const url = URL.createObjectURL(file);
    card.innerHTML = `
      <img src="${url}" alt="${file.name}" />
      <div class="preview-meta">
        <div title="${file.name}">${file.name}</div>
        <button type="button" class="btn btn--secondary btn--block" data-rmidx="${i}">移除</button>
      </div>
    `;
    const img = card.querySelector("img");
    img.addEventListener(
      "load",
      () => {
        URL.revokeObjectURL(url);
      },
      { once: true }
    );
    previewGrid.appendChild(card);
  }
  previewMore.textContent =
    selectedFiles.length > maxPreview ? `还有 ${selectedFiles.length - maxPreview} 个文件未展示` : "";
}

function updateMode() {
  const isConvert = modeSelect.value === "convert";
  compressToWrap.classList.toggle("hidden", isConvert);
  targetWrap.classList.toggle("hidden", !isConvert);
}

function getCurrentState() {
  return {
    mode: modeSelect.value,
    compressTo: compressToSelect.value,
    target: targetSelect.value,
    targetKb: targetSizeInput.value || "",
  };
}

function applyState(state = {}) {
  modeSelect.value = state.mode || "compress";
  compressToSelect.value = state.compressTo || "same";
  targetSelect.value = state.target || "jpeg";
  targetSizeInput.value = state.targetKb || "";
  updateMode();
}

function saveState() {
  localStorage.setItem(STORAGE_STATE, JSON.stringify(getCurrentState()));
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_STATE);
    if (raw) applyState(JSON.parse(raw));
  } catch (_e) {
    // Ignore corrupted cache.
  }
}

function saveHistory() {
  localStorage.setItem(STORAGE_HISTORY, JSON.stringify(historyItems.slice(0, 10)));
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_HISTORY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return;
    historyItems.length = 0;
    for (const item of parsed.slice(0, 10)) {
      if (item && typeof item === "object") historyItems.push(item);
    }
  } catch (_e) {
    // Ignore corrupted cache.
  }
}

function deriveTarget(file, state) {
  if (state.mode === "convert") return state.target;
  if (state.compressTo !== "same") return state.compressTo;
  const original = extOf(file.name);
  return MIME_BY_EXT[original] ? original : "jpeg";
}

function resolveTargetExt(rawExt) {
  if (mimeFromExt(rawExt)) return { ext: rawExt, fallbackNote: "" };
  return { ext: "png", fallbackNote: `浏览器不支持直接导出 ${rawExt}，已回退为 png` };
}

function replaceExt(name, newExt) {
  const idx = name.lastIndexOf(".");
  const stem = idx >= 0 ? name.slice(0, idx) : name;
  return `${stem}.${newExt}`;
}

async function fileToImageBitmap(file) {
  const blobUrl = URL.createObjectURL(file);
  try {
    return await createImageBitmap(file);
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
}

function canvasToBlob(canvas, mime, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("编码失败"));
        return;
      }
      resolve(blob);
    }, mime, quality);
  });
}

function drawToCanvas(bitmap, width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, width);
  canvas.height = Math.max(1, height);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function bitmapToImageData(bitmap, width = bitmap.width, height = bitmap.height) {
  const canvas = drawToCanvas(bitmap, width, height);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  return ctx.getImageData(0, 0, canvas.width, canvas.height);
}

/** MozJPEG / libwebp 使用 1–100 质量刻度。 */
function wasmQualityMin100(profile) {
  return profile === "preserve" ? 35 : 1;
}

/** WASM 有时返回整块内存缓冲，按文件头裁剪出真实 JPEG 长度。 */
function jpegPayloadByteLength(buf) {
  const u8 = new Uint8Array(buf);
  if (u8.length < 4 || u8[0] !== 0xff || u8[1] !== 0xd8) return u8.byteLength;
  for (let i = u8.length - 2; i >= 0; i -= 1) {
    if (u8[i] === 0xff && u8[i + 1] === 0xd9) return i + 2;
  }
  return u8.byteLength;
}

/** 按 RIFF 头裁剪 WebP 实际长度。 */
function webpPayloadByteLength(buf) {
  const u8 = new Uint8Array(buf);
  if (u8.length < 12 || u8[0] !== 0x52 || u8[1] !== 0x49 || u8[2] !== 0x46 || u8[3] !== 0x46) {
    return u8.byteLength;
  }
  const riffSize = u8[4] | (u8[5] << 8) | (u8[6] << 16) | (u8[7] << 24);
  const total = 8 + riffSize;
  if (!Number.isFinite(total) || total <= 8) return u8.byteLength;
  return Math.min(u8.byteLength, total);
}

function jpegWasmBufferToBlob(buf) {
  const u8 = new Uint8Array(buf);
  const n = jpegPayloadByteLength(buf);
  return new Blob([u8.subarray(0, n)], { type: "image/jpeg" });
}

function webpWasmBufferToBlob(buf) {
  const u8 = new Uint8Array(buf);
  const n = webpPayloadByteLength(buf);
  return new Blob([u8.subarray(0, n)], { type: "image/webp" });
}

async function encodeJpegWithMozjpeg(bitmap, targetBytes, profile, w, h) {
  const imageData = bitmapToImageData(bitmap, w, h);
  const mod = await import(JSQUASH_JPEG_ENCODE);
  const encode = mod.default;
  const qMin = wasmQualityMin100(profile);
  let lo = qMin;
  let hi = 100;
  let bestBlob = null;
  for (let i = 0; i < 28; i += 1) {
    if (lo > hi) break;
    const q = Math.floor((lo + hi + 1) / 2);
    const buf = await encode(imageData, {
      quality: q,
      progressive: true,
      optimize_coding: true,
      quant_table: 3,
    });
    const size = jpegPayloadByteLength(buf);
    if (size <= targetBytes) {
      bestBlob = jpegWasmBufferToBlob(buf);
      lo = q + 1;
    } else {
      hi = q - 1;
    }
  }
  if (bestBlob) {
    return { blob: bestBlob, met: true, note: `保持 ${w}×${h}px，MozJPEG(WASM) 质量调优` };
  }
  const lowBuf = await encode(imageData, {
    quality: qMin,
    progressive: true,
    optimize_coding: true,
    quant_table: 3,
  });
  const blob = jpegWasmBufferToBlob(lowBuf);
  const met = blob.size <= targetBytes;
  return {
    blob,
    met,
    note: met
      ? `保持 ${w}×${h}px，MozJPEG(WASM)`
      : `保持 ${w}×${h}px 时 JPEG 仍超出目标；请提高目标 KB`,
  };
}

async function encodeWebpWithWasm(bitmap, targetBytes, profile, w, h) {
  const imageData = bitmapToImageData(bitmap, w, h);
  const mod = await import(JSQUASH_WEBP_ENCODE);
  const encode = mod.default;
  const qMin = wasmQualityMin100(profile);

  const bufTry = await encode(imageData, {
    target_size: targetBytes,
    target_PSNR: 0,
    quality: 85,
    pass: profile === "preserve" ? 5 : 9,
    method: 6,
    lossless: 0,
    thread_level: 1,
  });
  let blob = webpWasmBufferToBlob(bufTry);
  if (blob.size <= targetBytes) {
    return { blob, met: true, note: `保持 ${w}×${h}px，libwebp(WASM) 目标体积模式` };
  }

  let lo = qMin;
  let hi = 100;
  let bestBlob = null;
  for (let i = 0; i < 28; i += 1) {
    if (lo > hi) break;
    const q = Math.floor((lo + hi + 1) / 2);
    const buf = await encode(imageData, {
      quality: q,
      target_size: 0,
      target_PSNR: 0,
      pass: 6,
      method: 6,
      lossless: 0,
    });
    if (webpPayloadByteLength(buf) <= targetBytes) {
      bestBlob = webpWasmBufferToBlob(buf);
      lo = q + 1;
    } else {
      hi = q - 1;
    }
  }
  if (bestBlob) {
    return { blob: bestBlob, met: true, note: `保持 ${w}×${h}px，libwebp(WASM) 质量调优` };
  }
  const lowBuf = await encode(imageData, {
    quality: qMin,
    target_size: 0,
    pass: 4,
    method: 6,
    lossless: 0,
  });
  blob = webpWasmBufferToBlob(lowBuf);
  const met = blob.size <= targetBytes;
  return {
    blob,
    met,
    note: met
      ? `保持 ${w}×${h}px，libwebp(WASM)`
      : `保持 ${w}×${h}px 时 WebP 仍超出目标；请提高目标 KB`,
  };
}

/**
 * 有损格式优先走 jSquash WASM（更小、更易达标）；失败时回退 canvas.toBlob。
 */
async function encodeLossyWasmOrCanvas(bitmap, mime, targetExt, targetBytes, profile, w, h) {
  try {
    const ext = String(targetExt || "").toLowerCase();
    if (ext === "webp") {
      return await encodeWebpWithWasm(bitmap, targetBytes, profile, w, h);
    }
    if (ext === "jpeg" || ext === "jpg") {
      return await encodeJpegWithMozjpeg(bitmap, targetBytes, profile, w, h);
    }
  } catch (err) {
    console.warn("WASM 编码失败，回退到 canvas.toBlob", err);
  }
  const canvas = drawToCanvas(bitmap, w, h);
  const qMin = lossyQualityMin(profile);
  return binarySearchQualityFullSize(canvas, mime, targetBytes, qMin);
}

async function encodeAtDimensions(bitmap, targetExt, targetBytes, profile, w, h) {
  const mime = mimeFromExt(targetExt);
  if (!mime) throw new Error(`不支持目标格式: ${targetExt}`);
  if (mime === "image/png") {
    const canvas = drawToCanvas(bitmap, w, h);
    const blob = await canvasToBlob(canvas, mime, undefined);
    const met = blob.size <= targetBytes;
    return {
      blob,
      met,
      extUsed: "png",
      note: met ? `保持 ${w}×${h}px，PNG 导出` : `PNG ${w}×${h}px 仍超出目标体积`,
    };
  }
  const result = await encodeLossyWasmOrCanvas(bitmap, mime, targetExt, targetBytes, profile, w, h);
  return { ...result, extUsed: targetExt };
}

function lossyQualityMin(profile) {
  return profile === "preserve" ? 0.35 : 0.01;
}

/**
 * 在「固定画布尺寸」上对 JPEG/WebP 二分质量：在不超过 targetBytes 的前提下尽量取较高质量。
 * 不缩小像素尺寸。
 */
async function binarySearchQualityFullSize(canvas, mime, targetBytes, qMin) {
  const qMax = 1;
  let bestUnder = null;
  let lo = qMin;
  let hi = qMax;
  for (let i = 0; i < 24; i += 1) {
    const mid = (lo + hi) / 2;
    const blob = await canvasToBlob(canvas, mime, mid);
    if (blob.size <= targetBytes) {
      bestUnder = blob;
      lo = mid;
    } else {
      hi = mid;
    }
  }
  const w = canvas.width;
  const h = canvas.height;
  if (bestUnder) {
    return { blob: bestUnder, met: true, note: `保持 ${w}×${h}px，质量已调优` };
  }
  const lowest = await canvasToBlob(canvas, mime, qMin);
  const met = lowest.size <= targetBytes;
  return {
    blob: lowest,
    met,
    note: met
      ? `保持 ${w}×${h}px，已用较低质量`
      : `保持 ${w}×${h}px 时即使最低可接受质量仍大于目标；请提高目标 KB 或改用 WebP/JPEG`,
  };
}

/**
 * 严格保持原始像素尺寸；优先目标格式，不达标时可自动回退到更易达标的有损格式。
 */
async function encodeToTarget(file, targetExt, targetBytes, profile = "aggressive") {
  const bitmap = await fileToImageBitmap(file);
  try {
    const first = await encodeAtDimensions(bitmap, targetExt, targetBytes, profile, bitmap.width, bitmap.height);
    if (first.met) {
      return first;
    }

    let best = first;
    const fallbackExts = ["webp", "jpeg"].filter((ext) => ext !== targetExt);
    for (const ext of fallbackExts) {
      const attempt = await encodeAtDimensions(bitmap, ext, targetBytes, profile, bitmap.width, bitmap.height);
      if (!best.blob || (attempt.blob && attempt.blob.size < best.blob.size)) best = attempt;
      if (attempt.met) {
        return {
          ...attempt,
          note: `${attempt.note}；严格达标已自动改为 ${ext}`,
        };
      }
    }

    return {
      ...best,
      met: false,
      note: `${best.note}；保持原尺寸条件下仍未达标，请提高目标 KB`,
    };
  } finally {
    bitmap.close();
  }
}

async function processOne(file, state, targetBytes, profile = "aggressive") {
  const preferredExt = deriveTarget(file, state);
  const { ext: targetExt, fallbackNote } = resolveTargetExt(preferredExt);
  const { blob, met, note, extUsed } = await encodeToTarget(file, targetExt, targetBytes, profile);
  const targetName = replaceExt(file.name, extUsed || targetExt);
  return {
    inputName: file.name,
    outputName: targetName,
    before: file.size,
    after: blob.size,
    met,
    note: fallbackNote ? `${note}; ${fallbackNote}` : note,
    blob,
  };
}

function renderRows(rows) {
  latestRows = rows.slice();
  resultBody.innerHTML = "";
  const mode = resultFilter ? resultFilter.value : "all";
  const showRows = rows.filter((row) => (mode === "met" ? row.met : mode === "unmet" ? !row.met : true));
  for (const row of showRows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.inputName}</td>
      <td>${bytesToKb(row.before)}</td>
      <td>${bytesToKb(row.after)}</td>
      <td><span class="status-tag ${row.met ? "ok" : "bad"}">${row.met ? "达标" : "未达标"}</span></td>
      <td>${row.note}</td>
    `;
    resultBody.appendChild(tr);
  }
  if (!rows.length) {
    summaryText.textContent = "暂无结果";
    failedNames = [];
    sumCount.textContent = "0";
    sumBefore.textContent = "0 KB";
    sumAfter.textContent = "0 KB";
    sumRatio.textContent = "0%";
    return;
  }
  const totalBefore = rows.reduce((s, r) => s + r.before, 0);
  const totalAfter = rows.reduce((s, r) => s + r.after, 0);
  const metCount = rows.filter((r) => r.met).length;
  failedNames = rows.filter((r) => !r.met).map((r) => r.inputName);
  const ratio = totalBefore ? (((totalBefore - totalAfter) / totalBefore) * 100).toFixed(1) : "0.0";
  sumCount.textContent = String(rows.length);
  sumBefore.textContent = bytesToKb(totalBefore);
  sumAfter.textContent = bytesToKb(totalAfter);
  sumRatio.textContent = `${ratio}%`;
  summaryText.textContent = `共 ${rows.length} 张，达标 ${metCount} 张，体积 ${bytesToKb(totalBefore)} -> ${bytesToKb(totalAfter)}`;
}

function currentFiles() {
  return selectedFiles.length ? selectedFiles : Array.from(imagesInput.files || []);
}

function addHistory(state, rows) {
  const metCount = rows.filter((r) => r.met).length;
  historyItems.unshift({
    at: new Date().toLocaleString(),
    state,
    text: `${state.mode}/${state.targetKb || "-"}KB｜${rows.length}张 / 达标${metCount}张`,
  });
  while (historyItems.length > 10) historyItems.pop();
  saveHistory();
  renderHistory();
}

function renderHistory() {
  historyList.innerHTML = "";
  historyText.textContent = historyItems.length ? "点击“复用参数”可一键套用" : "暂无历史任务";
  for (let i = 0; i < historyItems.length; i += 1) {
    const item = historyItems[i];
    const div = document.createElement("div");
    div.className = "list-item";
    div.innerHTML = `
      <span>${item.at}｜${item.text}</span>
      <button type="button" class="btn btn--secondary btn--compact" data-hidx="${i}">复用参数</button>
    `;
    historyList.appendChild(div);
  }
}

function applyPreset(value) {
  if (!value) return;
  if (value === "social") {
    applyState({ mode: "compress", compressTo: "jpeg", target: "jpeg", targetKb: "400" });
  } else if (value === "ecommerce") {
    applyState({ mode: "convert", compressTo: "same", target: "webp", targetKb: "800" });
  } else if (value === "archive") {
    applyState({ mode: "compress", compressTo: "same", target: "png", targetKb: "1024" });
  }
  saveState();
  refreshPreview();
  statusText.textContent = "已应用推荐参数";
}

async function runTask(files, state, options = {}) {
  const { updateOutputFiles = true, profile = "aggressive" } = options;
  if (!files.length) {
    statusText.textContent = "请先选择图片";
    return [];
  }
  const targetKb = Number(state.targetKb || 0);
  if (!Number.isFinite(targetKb) || targetKb <= 0) {
    statusText.textContent = "请填写有效目标体积(KB)";
    return [];
  }

  runBtn.disabled = true;
  downloadBtn.disabled = true;
  setProgress(0);
  statusText.textContent = "处理中...";
  latestSourceFiles = files.slice();
  const rows = [];
  const produced = [];
  const targetBytes = Math.floor(targetKb * 1024);

  for (let i = 0; i < files.length; i += 1) {
    const file = files[i];
    try {
      const row = await processOne(file, state, targetBytes, profile);
      rows.push(row);
      produced.push({ name: row.outputName, blob: row.blob });
    } catch (err) {
      rows.push({
        inputName: file.name,
        outputName: "-",
        before: file.size,
        after: 0,
        met: false,
        note: `失败: ${err && err.message ? err.message : "未知错误"}`,
      });
    }
    setProgress(((i + 1) / files.length) * 100);
  }

  if (updateOutputFiles) outputFiles = produced;
  renderRows(rows);
  statusText.textContent = "处理完成";
  runBtn.disabled = false;
  downloadBtn.disabled = outputFiles.length === 0;
  addHistory(state, rows);
  return rows;
}

async function runCurrent() {
  const files = currentFiles();
  const state = getCurrentState();
  saveState();
  await runTask(files, state, { updateOutputFiles: true, profile: "aggressive" });
}

function exportCsv() {
  if (!latestRows.length) {
    statusText.textContent = "暂无结果可导出";
    return;
  }
  const header = ["文件", "原始KB", "输出KB", "达标", "说明"];
  const lines = [header.join(",")];
  for (const row of latestRows) {
    lines.push(
      [
        row.inputName,
        (row.before / 1024).toFixed(2),
        (row.after / 1024).toFixed(2),
        row.met ? "是" : "否",
        `"${String(row.note || "").replaceAll('"', '""')}"`,
      ].join(",")
    );
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "results.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

async function retryFailed() {
  if (!failedNames.length) {
    statusText.textContent = "没有可重试的失败项";
    return;
  }
  const source = latestSourceFiles.length ? latestSourceFiles : currentFiles();
  const retryFiles = source.filter((f) => failedNames.includes(f.name));
  if (!retryFiles.length) {
    statusText.textContent = "当前文件列表中未找到失败项，请重新选择文件";
    return;
  }
  await runTask(retryFiles, getCurrentState(), { updateOutputFiles: true, profile: "aggressive" });
}

async function downloadZip() {
  if (!outputFiles.length) return;
  downloadBtn.disabled = true;
  statusText.textContent = "正在打包 ZIP...";
  const zip = new JSZip();
  outputFiles.forEach((f) => zip.file(f.name, f.blob));
  const blob = await zip.generateAsync({ type: "blob", compression: "DEFLATE", compressionOptions: { level: 6 } });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "processed_images.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
  statusText.textContent = "ZIP 已下载";
  downloadBtn.disabled = false;
}

function refreshPreview() {
  // 策略预览功能已移除，保留空函数以兼容现有调用点。
}

async function readEntryRecursive(entry) {
  if (!entry) return [];
  if (entry.isFile) {
    return new Promise((resolve) => {
      entry.file(
        (file) => resolve([file]),
        () => resolve([])
      );
    });
  }
  if (entry.isDirectory) {
    const reader = entry.createReader();
    const children = [];
    while (true) {
      const batch = await new Promise((resolve) => reader.readEntries(resolve));
      if (!batch.length) break;
      children.push(...batch);
    }
    const nested = await Promise.all(children.map((child) => readEntryRecursive(child)));
    return nested.flat();
  }
  return [];
}

modeSelect.addEventListener("change", () => {
  updateMode();
  saveState();
  refreshPreview();
});
compressToSelect.addEventListener("change", () => {
  saveState();
  refreshPreview();
});
targetSelect.addEventListener("change", () => {
  saveState();
  refreshPreview();
});
targetSizeInput.addEventListener("input", () => {
  saveState();
  refreshPreview();
});
runBtn.addEventListener("click", runCurrent);
downloadBtn.addEventListener("click", downloadZip);
resultFilter.addEventListener("change", () => renderRows(latestRows));
presetSelect.addEventListener("change", () => applyPreset(presetSelect.value));
clearAllBtn.addEventListener("click", () => {
  selectedFiles = [];
  imagesInput.value = "";
  outputFiles = [];
  latestRows = [];
  latestSourceFiles = [];
  failedNames = [];
  setProgress(0);
  updateFileMeta();
  renderRows([]);
  refreshPreview();
  statusText.textContent = "已清空";
  downloadBtn.disabled = true;
});
retryFailedBtn.addEventListener("click", retryFailed);
exportCsvBtn.addEventListener("click", exportCsv);
imagesInput.addEventListener("change", () => setSelectedFiles(Array.from(imagesInput.files || [])));
pickFilesBtn.addEventListener("click", () => imagesInput.click());

historyList.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const idxRaw = target.getAttribute("data-hidx");
  if (idxRaw == null) return;
  const item = historyItems[Number(idxRaw)];
  if (!item) return;
  applyState(item.state);
  saveState();
  refreshPreview();
  statusText.textContent = "已复用历史参数";
});

previewGrid.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const idxRaw = target.getAttribute("data-rmidx");
  if (idxRaw == null) return;
  const idx = Number(idxRaw);
  if (Number.isNaN(idx) || idx < 0 || idx >= selectedFiles.length) return;
  selectedFiles.splice(idx, 1);
  updateFileMeta();
  refreshPreview();
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("drag");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("drag");
  });
});
dropZone.addEventListener("drop", async (event) => {
  const dt = event.dataTransfer;
  if (!dt) return;
  let files = [];
  if (dt.items && dt.items.length && dt.items[0].webkitGetAsEntry) {
    const entries = Array.from(dt.items)
      .map((item) => item.webkitGetAsEntry && item.webkitGetAsEntry())
      .filter(Boolean);
    const all = await Promise.all(entries.map((entry) => readEntryRecursive(entry)));
    files = all.flat();
  } else {
    files = Array.from(dt.files || []);
  }
  setSelectedFiles(files);
  statusText.textContent = selectedFiles.length ? "已读取拖拽文件，可开始处理" : "未识别到可处理图片";
});

loadState();
loadHistory();
updateMode();
setSelectedFiles([]);
renderRows([]);
renderHistory();
refreshPreview();
