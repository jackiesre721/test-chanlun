import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AnalyzeResult, GlmVerdict } from "@/types/analysis";
import { postVerdict } from "@/lib/api";
import { useSettingsStore } from "@/stores/settings-store";

interface GlmState {
  apiKey: string;
  model: string;
  fullContext: boolean;
  useGlm: boolean;
  verdict: GlmVerdict | null;
  loading: boolean;
  error: string | null;
  setApiKey: (k: string) => void;
  setModel: (m: string) => void;
  setFullContext: (v: boolean) => void;
  setUseGlm: (v: boolean) => void;
  fetchVerdict: (result: AnalyzeResult, signal?: AbortSignal) => Promise<void>;
  clearVerdict: () => void;
}

export const useGlmStore = create<GlmState>()(
  persist(
    (set, get) => ({
      apiKey: "",
      model: "glm-4.7",
      fullContext: true,
      useGlm: true,
      verdict: null,
      loading: false,
      error: null,

      setApiKey: (k) => set({ apiKey: k }),
      setModel: (m) => set({ model: m }),
      setFullContext: (v) => set({ fullContext: v }),
      setUseGlm: (v) => set({ useGlm: v }),

      fetchVerdict: async (result, signal) => {
        if (!get().useGlm) return;
        set({ loading: true, error: null, verdict: null });
        try {
          const { apiKey, model, fullContext } = get();
          const { symbol, interval } = useSettingsStore.getState();
          // 后端 `verdict_from_analyze_payload` 按完整 `AnalyzeResponse` 校验；须传分析接口同源 JSON + glm_* 选项。
          const clone = JSON.parse(JSON.stringify(result)) as Record<string, unknown>;
          clone.market = clone.market ?? "crypto";
          clone.symbol =
            typeof clone.symbol === "string" && clone.symbol
              ? clone.symbol
              : symbol;
          const iv = clone.interval;
          clone.interval =
            iv === undefined || iv === null || iv === ""
              ? interval
              : typeof iv === "number"
                ? String(iv)
                : String(iv);

          const body: Record<string, unknown> = {
            ...clone,
            glm_full_context: fullContext,
            glm_model: model,
          };
          const trimmed = apiKey.trim();
          if (trimmed) body.glm_api_key = trimmed;

          const text = await postVerdict(body, signal);
          set({ verdict: { raw: text }, loading: false });
        } catch (e: unknown) {
          if (e instanceof DOMException && e.name === "AbortError") return;
          set({ error: (e as Error).message, loading: false });
        }
      },

      clearVerdict: () => set({ verdict: null, loading: false, error: null }),
    }),
    {
      name: "chanlan_glm",
      partialize: (s) => ({ apiKey: s.apiKey, model: s.model, fullContext: s.fullContext, useGlm: s.useGlm }),
    },
  ),
);
