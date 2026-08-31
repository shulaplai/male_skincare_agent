/* 相片壓縮 —— 上載前喺瀏覽器壓縮，慳 localStorage 空間 */

const MAX_DIM = 1024;
const QUALITY = 0.78;

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result));
    fr.onerror = () => reject(new Error('讀取檔案失敗'));
    fr.readAsDataURL(file);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('圖片載入失敗（可能唔係圖片檔）'));
    img.src = src;
  });
}

/**
 * 將圖片壓縮成 JPEG dataURL。
 * 原圖細過 300KB 且唔超過 maxDim 就唔郁，直接回傳。
 */
export async function compressImage(
  file: File,
  maxDim = MAX_DIM,
  quality = QUALITY,
): Promise<string> {
  const raw = await readAsDataURL(file);
  const img = await loadImage(raw);
  const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
  if (scale >= 1 && file.size < 300_000) return raw;

  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(img.width * scale));
  canvas.height = Math.max(1, Math.round(img.height * scale));
  const ctx = canvas.getContext('2d');
  if (!ctx) return raw;
  ctx.fillStyle = '#f4efe6';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', quality);
}
