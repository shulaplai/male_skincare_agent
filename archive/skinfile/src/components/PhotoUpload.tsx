/* 相片上載：選檔 → 壓縮 → dataURL */

import { useRef, useState } from 'react';
import { compressImage } from '../lib/compressImage';

export function PhotoUpload({
  value,
  onChange,
  label = '上載相片',
  hint,
}: {
  value?: string;
  onChange: (dataUrl: string | undefined) => void;
  label?: string;
  hint?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File | undefined) => {
    setError(null);
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('請選擇圖片檔案。');
      return;
    }
    setBusy(true);
    try {
      const dataUrl = await compressImage(file);
      onChange(dataUrl);
    } catch (e) {
      setError(e instanceof Error ? e.message : '相片處理失敗');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      {value ? (
        <div className="photo-frame" style={{ maxWidth: 320, aspectRatio: '1/1', marginBottom: 10 }}>
          <img src={value} alt="已上載相片" />
          <button
            type="button"
            className="btn sm danger"
            style={{ position: 'absolute', top: 8, right: 8 }}
            onClick={() => onChange(undefined)}
          >
            移除
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="btn ghost"
          style={{ borderStyle: 'dashed', width: '100%', maxWidth: 320, padding: '34px 12px', flexDirection: 'column', gap: 6 }}
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          <span style={{ fontSize: 22 }}>📷</span>
          <span>{busy ? '處理中…' : label}</span>
          {hint ? <span className="muted" style={{ fontSize: 12 }}>{hint}</span> : null}
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          void handleFile(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
      {error ? <div className="muted" style={{ color: 'var(--danger)', fontSize: 12.5, marginTop: 6 }}>{error}</div> : null}
    </div>
  );
}
