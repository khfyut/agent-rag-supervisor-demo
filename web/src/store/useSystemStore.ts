// 系统状态（provider/model、KB/DB 就绪、报告数），供状态条使用。

import { create } from "zustand";
import { fetchStatus } from "../api/client";
import type { SystemStatus } from "../types";

interface SystemState {
  status: SystemStatus | null;
  error: boolean;
  loading: boolean;
  load: () => Promise<void>;
}

export const useSystemStore = create<SystemState>((set) => ({
  status: null,
  error: false,
  loading: false,
  load: async () => {
    set({ loading: true });
    try {
      const status = await fetchStatus();
      set({ status, error: false, loading: false });
    } catch {
      set({ error: true, loading: false });
    }
  },
}));
