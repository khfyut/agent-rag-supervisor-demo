import { useRef, useState, type DragEvent } from "react";
import { ErrorNotice } from "../../components";

const MAX_BYTES = 1024 * 1024; // 1MB
const ALLOWED_EXT = [".md", ".txt"];

export function validateFile(file: File): string | null {
  const lower = file.name.toLowerCase();
  if (!ALLOWED_EXT.some((ext) => lower.endsWith(ext))) {
    return `仅支持 .md / .txt 文件（收到 ${file.name}）`;
  }
  if (file.size > MAX_BYTES) {
    return `单文件不能超过 1MB（${file.name} 为 ${(file.size / 1024 / 1024).toFixed(2)}MB）`;
  }
  return null;
}

export interface UploadZoneProps {
  onUploaded: (file: File) => Promise<void>;
}

export function UploadZone({ onUploaded }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);
    for (const file of Array.from(files)) {
      const invalid = validateFile(file);
      if (invalid) {
        setError(invalid);
        return;
      }
    }
    setBusy(true);
    try {
      for (const file of Array.from(files)) {
        await onUploaded(file);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    void handleFiles(e.dataTransfer.files);
  };

  return (
    <div>
      <div
        className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-8 text-center transition ${
          dragOver ? "border-indigo-400 bg-indigo-50" : "border-slate-300 bg-slate-50 hover:border-indigo-300 hover:bg-indigo-50/50"
        }`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        data-testid="upload-zone"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".md,.txt"
          multiple
          className="hidden"
          onChange={(e) => void handleFiles(e.target.files)}
          data-testid="upload-input"
        />
        <div className="text-3xl">📄</div>
        <div className="mt-2 text-sm font-medium text-slate-700">
          {busy ? "上传中…" : "拖拽文件到此处，或点击选择"}
        </div>
        <div className="mt-1 text-xs text-slate-400">仅支持 .md / .txt，单文件 ≤ 1MB</div>
      </div>
      {error ? <div className="mt-2"><ErrorNotice message={error} /></div> : null}
    </div>
  );
}
