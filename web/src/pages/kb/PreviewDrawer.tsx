import { useEffect, useState } from "react";
import { fetchKbDoc } from "../../api/client";
import { Loading, MarkdownAnswer } from "../../components";

export interface PreviewDrawerProps {
  filename: string | null;
  onClose: () => void;
}

export function PreviewDrawer({ filename, onClose }: PreviewDrawerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!filename) {
      setContent(null);
      setError(null);
      return;
    }
    setContent(null);
    setError(null);
    fetchKbDoc(filename)
      .then((doc) => setContent(doc.content))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [filename]);

  if (!filename) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" role="dialog" data-testid="preview-drawer">
      <div className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-mono text-base font-semibold text-slate-900">{filename}</h3>
          <button
            className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-100"
            onClick={onClose}
            aria-label="关闭预览"
          >
            ✕
          </button>
        </div>
        {error ? <div className="text-sm text-rose-600">加载失败：{error}</div> : null}
        {!content && !error ? <Loading text="文档加载中…" /> : null}
        {content ? <MarkdownAnswer content={content} /> : null}
      </div>
    </div>
  );
}
