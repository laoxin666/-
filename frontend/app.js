const imagesInput = document.getElementById("imagesInput");
const modeSelect = document.getElementById("modeSelect");
const compressToSelect = document.getElementById("compressToSelect");
const targetSelect = document.getElementById("targetSelect");
const targetSizeInput = document.getElementById("targetSizeInput");
const runBtn = document.getElementById("runBtn");
const enqueueBtn = document.getElementById("enqueueBtn");
const downloadBtn = document.getElementById("downloadBtn");
const statusText = document.getElementById("statusText");
const progressBar = document.getElementById("progressBar");
const resultBody = document.getElementById("resultBody");
const summaryText = document.getElementById("summaryText");
const compressToWrap = document.getElementById("compressToWrap");
const targetWrap = document.getElementById("targetWrap");
const dropZone = document.getElementById("dropZone");
const fileMeta = document.getElementById("fileMeta");
const presetSelect = document.getElementById("presetSelect");
const clearAllBtn = document.getElementById("clearAllBtn");
const resultFilter = document.getElementById("resultFilter");
const retryFailedBtn = document.getElementById("retryFailedBtn");
const exportCsvBtn = document.getElementById("exportCsvBtn");
const queueText = document.getElementById("queueText");
const queueList = document.getElementById("queueList");
const clearPendingBtn = document.getElementById("clearPendingBtn");
const historyText = document.getElementById("historyText");
const historyList = document.getElementById("historyList");
const refreshPreviewBtn = document.getElementById("refreshPreviewBtn");
const previewStatus = document.getElementById("previewStatus");
const previewCards = document.getElementById("previewCards");
const previewGrid = document.getElementById("previewGrid");
const previewMore = document.getElementById("previewMore");
const sumCount = document.getElementById("sumCount");
const sumBefore = document.getElementById("sumBefore");
const sumAfter = document.getElementById("sumAfter");
const sumRatio = document.getElementById("sumRatio");

const STORAGE_STATE = "imgTool.frontend.state";
const STORAGE_HISTORY = "imgTool.frontend.history";

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
const taskQueue = [];
let queueRunning = false;
let taskSeq = 1;
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
        <button type="button" data-rmidx="${i}">移除</button>
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

function candidateSet(profile, mime) {
  if (profile === "preserve") {
    return {
      scales: [1, 0.95, 0.9, 0.85, 0.8, 0.75],
      qualities: mime === "image/png" ? [undefined] : [0.96, 0.9, 0.84, 0.78, 0.72, 0.66],
    };
  }
  return {
    scales: [1, 0.92, 0.86, 0.8, 0.74, 0.68, 0.62, 0.56],
    qualities: mime === "image/png" ? [undefined] : [0.92, 0.86, 0.8, 0.74, 0.68, 0.62, 0.56, 0.5, 0.44],
  };
}

async function encodeToTarget(file, targetExt, targetBytes, profile = "aggressive") {
  const mime = mimeFromExt(targetExt);
  if (!mime) throw new Error(`不支持目标格式: ${targetExt}`);
  const bitmap = await fileToImageBitmap(file);
  try {
    let bestBlob = null;
    let bestLabel = "保持原图";
    const { scales, qualities } = candidateSet(profile, mime);

    for (const scale of scales) {
      const width = Math.max(1, Math.floor(bitmap.width * scale));
      const height = Math.max(1, Math.floor(bitmap.height * scale));
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(bitmap, 0, 0, width, height);

      for (const q of qualities) {
        const blob = await canvasToBlob(canvas, mime, q);
        if (!bestBlob || blob.size < bestBlob.size) {
          bestBlob = blob;
          bestLabel = scale === 1 ? "质量压缩" : `质量压缩+缩放(${Math.round(scale * 100)}%)`;
        }
        if (blob.size <= targetBytes) {
          return { blob, met: true, note: bestLabel };
        }
      }
    }
    return { blob: bestBlob, met: bestBlob ? bestBlob.size <= targetBytes : false, note: bestLabel };
  } finally {
    bitmap.close();
  }
}

async function processOne(file, state, targetBytes, profile = "aggressive") {
  const preferredExt = deriveTarget(file, state);
  const { ext: targetExt, fallbackNote } = resolveTargetExt(preferredExt);
  const targetName = replaceExt(file.name, targetExt);
  const { blob, met, note } = await encodeToTarget(file, targetExt, targetBytes, profile);
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
      <button type="button" class="mini-btn" data-hidx="${i}">复用参数</button>
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
  enqueueBtn.disabled = true;
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
  enqueueBtn.disabled = false;
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

function renderQueue() {
  queueList.innerHTML = "";
  if (!taskQueue.length) {
    queueText.textContent = "队列为空";
    return;
  }
  queueText.textContent = `队列中 ${taskQueue.length} 项`;
  for (let i = 0; i < taskQueue.length; i += 1) {
    const task = taskQueue[i];
    const div = document.createElement("div");
    div.className = "list-item";
    div.innerHTML = `
      <span>#${i + 1}｜${task.files.length}张｜${task.state.mode}/${task.state.targetKb || "-"}KB｜${task.status}</span>
      <button type="button" class="mini-btn" data-qidx="${task.id}">移除</button>
    `;
    queueList.appendChild(div);
  }
}

async function runQueue() {
  if (queueRunning) return;
  queueRunning = true;
  while (taskQueue.length) {
    const task = taskQueue[0];
    task.status = "运行中";
    renderQueue();
    await runTask(task.files, task.state, { updateOutputFiles: true, profile: "aggressive" });
    taskQueue.shift();
    renderQueue();
  }
  queueRunning = false;
}

function enqueueCurrentTask() {
  const files = currentFiles();
  if (!files.length) {
    statusText.textContent = "请先选择图片";
    return;
  }
  const state = getCurrentState();
  saveState();
  taskQueue.push({
    id: taskSeq++,
    files: files.slice(),
    state,
    status: "等待中",
  });
  renderQueue();
  runQueue();
}

function clearPendingTasks() {
  for (let i = taskQueue.length - 1; i >= 0; i -= 1) {
    if (taskQueue[i].status !== "运行中") taskQueue.splice(i, 1);
  }
  renderQueue();
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

function estimateStrategy(files, state, ratio, label) {
  const targetKb = Number(state.targetKb || 0);
  const targetBytes = Math.floor(targetKb * 1024);
  const sampled = files.slice(0, 3);
  if (!sampled.length || targetBytes <= 0) return null;
  let totalBefore = 0;
  let totalAfter = 0;
  let unmet = 0;
  for (const f of sampled) {
    const before = f.size || 0;
    const after = Math.max(1024, Math.floor(before * ratio));
    totalBefore += before;
    totalAfter += after;
    if (after > targetBytes) unmet += 1;
  }
  const saved = totalBefore - totalAfter;
  const ratioPct = totalBefore ? ((saved / totalBefore) * 100).toFixed(1) : "0.0";
  return { label, after: totalAfter, ratioPct, unmet, sampled: sampled.length };
}

function refreshPreview() {
  const files = currentFiles();
  const state = getCurrentState();
  previewCards.innerHTML = "";
  const targetKb = Number(state.targetKb || 0);
  if (!files.length || !Number.isFinite(targetKb) || targetKb <= 0) {
    previewStatus.textContent = "请选择图片并填写目标体积";
    return;
  }
  const candidates = [
    estimateStrategy(files, state, 0.58, "严格达标优先"),
    estimateStrategy(files, state, 0.72, "内容保真优先"),
  ].filter(Boolean);
  if (!candidates.length) {
    previewStatus.textContent = "暂无预览数据";
    return;
  }
  for (const item of candidates) {
    const card = document.createElement("div");
    card.className = "preview-card";
    card.innerHTML = `
      <div class="preview-title">${item.label}</div>
      <div class="preview-metric">预计输出：${bytesToKb(item.after)}</div>
      <div class="preview-metric">预计节省：+${item.ratioPct}%</div>
      <div class="preview-metric">未达标：${item.unmet} 张</div>
    `;
    previewCards.appendChild(card);
  }
  previewStatus.textContent = `基于 ${Math.min(files.length, 3)} 张样本的快速估算`;
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
enqueueBtn.addEventListener("click", enqueueCurrentTask);
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
clearPendingBtn.addEventListener("click", clearPendingTasks);
refreshPreviewBtn.addEventListener("click", refreshPreview);
imagesInput.addEventListener("change", () => setSelectedFiles(Array.from(imagesInput.files || [])));

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

queueList.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const idRaw = target.getAttribute("data-qidx");
  if (idRaw == null) return;
  const id = Number(idRaw);
  const idx = taskQueue.findIndex((t) => t.id === id);
  if (idx < 0) return;
  if (taskQueue[idx].status === "运行中") {
    statusText.textContent = "当前运行任务不可移除";
    return;
  }
  taskQueue.splice(idx, 1);
  renderQueue();
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
renderQueue();
renderHistory();
refreshPreview();
