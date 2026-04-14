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

let outputFiles = [];

const MIME_BY_EXT = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
};

function updateMode() {
  const isConvert = modeSelect.value === "convert";
  compressToWrap.classList.toggle("hidden", isConvert);
  targetWrap.classList.toggle("hidden", !isConvert);
}

function setProgress(value) {
  const v = Math.max(0, Math.min(100, value));
  progressBar.style.width = `${v}%`;
}

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

function deriveTarget(file) {
  if (modeSelect.value === "convert") {
    return targetSelect.value;
  }
  const compressTo = compressToSelect.value;
  if (compressTo !== "same") return compressTo;
  const original = extOf(file.name);
  return MIME_BY_EXT[original] ? original : "jpeg";
}

function resolveTargetExt(rawExt) {
  if (mimeFromExt(rawExt)) {
    return { ext: rawExt, fallbackNote: "" };
  }
  return {
    ext: "png",
    fallbackNote: `浏览器不支持直接导出 ${rawExt}，已回退为 png`,
  };
}

function replaceExt(name, newExt) {
  const idx = name.lastIndexOf(".");
  const stem = idx >= 0 ? name.slice(0, idx) : name;
  return `${stem}.${newExt}`;
}

async function fileToImageBitmap(file) {
  const blobUrl = URL.createObjectURL(file);
  try {
    const img = await createImageBitmap(file);
    return img;
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

async function encodeToTarget(file, targetExt, targetBytes) {
  const mime = mimeFromExt(targetExt);
  if (!mime) throw new Error(`不支持目标格式: ${targetExt}`);
  const bitmap = await fileToImageBitmap(file);
  try {
    let bestBlob = null;
    let bestLabel = "保持原图";

    const scaleCandidates = [1, 0.92, 0.86, 0.8, 0.74, 0.68, 0.62, 0.56];
    const qualityCandidates = mime === "image/png" ? [undefined] : [0.92, 0.86, 0.8, 0.74, 0.68, 0.62, 0.56, 0.5, 0.44];

    for (const scale of scaleCandidates) {
      const width = Math.max(1, Math.floor(bitmap.width * scale));
      const height = Math.max(1, Math.floor(bitmap.height * scale));
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(bitmap, 0, 0, width, height);

      for (const q of qualityCandidates) {
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

async function processOne(file, targetBytes) {
  const preferredExt = deriveTarget(file);
  const { ext: targetExt, fallbackNote } = resolveTargetExt(preferredExt);
  const targetName = replaceExt(file.name, targetExt);
  const { blob, met, note } = await encodeToTarget(file, targetExt, targetBytes);
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
  resultBody.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.inputName}</td>
      <td>${bytesToKb(row.before)}</td>
      <td>${bytesToKb(row.after)}</td>
      <td>${row.met ? "是" : "否"}</td>
      <td>${row.note}</td>
    `;
    resultBody.appendChild(tr);
  }
  const totalBefore = rows.reduce((s, r) => s + r.before, 0);
  const totalAfter = rows.reduce((s, r) => s + r.after, 0);
  const metCount = rows.filter((r) => r.met).length;
  summaryText.textContent = `共 ${rows.length} 张，达标 ${metCount} 张，体积 ${bytesToKb(totalBefore)} -> ${bytesToKb(totalAfter)}`;
}

async function run() {
  const files = Array.from(imagesInput.files || []);
  if (!files.length) {
    statusText.textContent = "请先选择图片";
    return;
  }
  const targetKb = Number(targetSizeInput.value || 0);
  if (!Number.isFinite(targetKb) || targetKb <= 0) {
    statusText.textContent = "请填写有效目标体积(KB)";
    return;
  }

  runBtn.disabled = true;
  downloadBtn.disabled = true;
  setProgress(0);
  statusText.textContent = "处理中...";
  outputFiles = [];
  const rows = [];
  const targetBytes = Math.floor(targetKb * 1024);

  for (let i = 0; i < files.length; i += 1) {
    const file = files[i];
    try {
      const row = await processOne(file, targetBytes);
      rows.push(row);
      outputFiles.push({ name: row.outputName, blob: row.blob });
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

  renderRows(rows);
  statusText.textContent = "处理完成";
  runBtn.disabled = false;
  downloadBtn.disabled = outputFiles.length === 0;
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

modeSelect.addEventListener("change", updateMode);
runBtn.addEventListener("click", run);
downloadBtn.addEventListener("click", downloadZip);
updateMode();
