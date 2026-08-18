// 知识库文档 / 重建状态（页面层可自行管理状态，本 store 供需要时复用）。

import { create } from "zustand";
import {
  deleteKbDoc,
  fetchKbDocs,
  searchKb,
  streamKbRebuild,
  uploadKbDoc,
} from "../api/client";
import type { KbBuildEvent, KbDoc, KbSearchResult } from "../types";

export type KbBuildStatus = "idle" | "running" | "done" | "error";

interface KbState {
  docs: KbDoc[] | null;
  dirty: boolean;
  buildStatus: KbBuildStatus;
  buildProgress: { current: number; total: number; filename: string; chunks: number } | null;
  searchResults: KbSearchResult[] | null;
  error: string | null;
  loadDocs: () => Promise<void>;
  upload: (file: File) => Promise<void>;
  remove: (name: string) => Promise<void>;
  rebuild: () => void;
  search: (query: string, k: number) => Promise<void>;
  clearSearch: () => void;
}

export const useKbStore = create<KbState>((set) => ({
  docs: null,
  dirty: false,
  buildStatus: "idle",
  buildProgress: null,
  searchResults: null,
  error: null,

  loadDocs: async () => {
    try {
      const resp = await fetchKbDocs();
      set({ docs: resp.docs, dirty: resp.dirty, error: null });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    }
  },

  upload: async (file) => {
    try {
      const resp = await uploadKbDoc(file);
      set({ docs: resp.docs, dirty: true, error: null });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    }
  },

  remove: async (name) => {
    try {
      const resp = await deleteKbDoc(name);
      set({ docs: resp.docs, dirty: true, error: null });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    }
  },

  rebuild: () => {
    set({ buildStatus: "running", buildProgress: null, error: null });
    streamKbRebuild((event: KbBuildEvent) => {
      if (event.type === "kb_build_start") {
        set({ buildProgress: { current: 0, total: event.total_files, filename: "", chunks: 0 } });
      } else if (event.type === "kb_build_file") {
        set({
          buildProgress: {
            current: event.current,
            total: event.total,
            filename: event.filename,
            chunks: event.chunks,
          },
        });
      } else if (event.type === "kb_build_done") {
        set({ buildStatus: "done", dirty: false });
        void useKbStore.getState().loadDocs();
      } else if (event.type === "kb_build_error") {
        set({ buildStatus: "error", error: event.message });
      }
    });
  },

  search: async (query, k) => {
    try {
      const resp = await searchKb(query, k);
      set({ searchResults: resp.results, error: null });
    } catch (err) {
      set({ searchResults: null, error: err instanceof Error ? err.message : String(err) });
    }
  },

  clearSearch: () => set({ searchResults: null }),
}));
