import { useCallback, useEffect, useState } from "react";
import { deleteKbDoc, fetchKbDocs, formatSize, uploadKbDoc } from "../api/client";
import { Empty, ErrorNotice, Layout, Loading, Section } from "../components";
import type { KbDoc } from "../types";
import { PreviewDrawer } from "./kb/PreviewDrawer";
import { RebuildPanel } from "./kb/RebuildPanel";
import { SearchTestbed } from "./kb/SearchTestbed";
import { UploadZone } from "./kb/UploadZone";

export default function KbPage() {
  const [docs, setDocs] = useState<KbDoc[] | null>(null);
  const [dirty, setDirty] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [previewName, setPreviewName] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<KbDoc | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const resp = await fetchKbDocs();
      setDocs(resp.docs);
      setDirty(resp.dirty);
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleUpload = async (file: File) => {
    const resp = await uploadKbDoc(file);
    setDocs(resp.docs);
    setDirty(resp.dirty);
  };

  const handleDelete = async () => {
    if (!pendingDelete) return;
    setBusy(true);
    try {
      const resp = await deleteKbDoc(pendingDelete.name);
      setDocs(resp.docs);
      setDirty(resp.dirty);
      setPendingDelete(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRebuildDone = () => {
    void load();
  };

  return (
    <Layout>
      <div className="space-y-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">知识库管理</h1>
          <p className="mt-1 text-sm text-slate-500">
            管理 data/kb 文档：上传 / 删除 / 重建向量库 / 检索测试台
          </p>
        </div>

        {loadError ? <ErrorNotice message={loadError} /> : null}

        <Section title="文档上传" desc="支持 .md / .txt，单文件 ≤ 1MB；上传后需重建向量库" >
          <UploadZone onUploaded={handleUpload} />
        </Section>

        <Section title="重建向量库" desc="全量重建：清空 collection → 逐文件切块 → 向量化 → 写入 Chroma">
          <RebuildPanel dirty={dirty} onDone={handleRebuildDone} />
        </Section>

        <Section
          title="文档列表"
          desc="文件名 / 大小 / 修改时间 / 重建后的分片数（chunk_count）"
        >
          {!docs ? (
            <Loading />
          ) : docs.length === 0 ? (
            <Empty text="知识库目录为空，先上传文档" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs text-slate-500">
                    <th className="py-2 pr-3">文件名</th>
                    <th className="py-2 pr-3">大小</th>
                    <th className="py-2 pr-3">修改时间</th>
                    <th className="py-2 pr-3">分片数</th>
                    <th className="py-2 pr-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((doc) => (
                    <tr key={doc.name} className="border-b border-slate-100" data-testid="doc-row">
                      <td className="py-2 pr-3">
                        <button
                          className="font-mono text-slate-800 hover:text-indigo-700 hover:underline"
                          onClick={() => setPreviewName(doc.name)}
                        >
                          {doc.name}
                        </button>
                      </td>
                      <td className="py-2 pr-3 text-slate-600">{formatSize(doc.size)}</td>
                      <td className="py-2 pr-3 text-slate-600">{doc.modified_at}</td>
                      <td className="py-2 pr-3 text-slate-600">
                        {doc.chunk_count === null ? <span className="text-slate-400">未重建</span> : doc.chunk_count}
                      </td>
                      <td className="py-2 pr-3 text-right">
                        <button
                          className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-500 hover:bg-slate-50"
                          onClick={() => setPreviewName(doc.name)}
                        >
                          预览
                        </button>
                        <button
                          className="ml-2 rounded-lg border border-rose-200 px-2 py-1 text-xs text-rose-600 hover:bg-rose-50"
                          onClick={() => setPendingDelete(doc)}
                          data-testid="delete-doc"
                        >
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title="检索测试台" desc="向量检索 top-k + 引用核验（演示 Guardrail 的 verify 逻辑）">
          <SearchTestbed />
        </Section>
      </div>

      <PreviewDrawer filename={previewName} onClose={() => setPreviewName(null)} />

      {pendingDelete ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          role="dialog"
          data-testid="delete-confirm"
        >
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-semibold text-slate-900">确认删除文档？</h3>
            <p className="mt-2 break-all font-mono text-sm text-slate-600">{pendingDelete.name}</p>
            <p className="mt-1 text-xs text-slate-400">
              删除后需重建向量库，该文档的分片才会从检索中移除。
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                onClick={() => setPendingDelete(null)}
                disabled={busy}
              >
                取消
              </button>
              <button
                className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
                onClick={() => void handleDelete()}
                disabled={busy}
                data-testid="confirm-delete"
              >
                {busy ? "删除中…" : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </Layout>
  );
}
