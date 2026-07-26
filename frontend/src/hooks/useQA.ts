import { useCallback, useState } from "react";
import { parseApi } from "../lib/validate";
import { QAResponseSchema } from "../schemas/api";
import type { QAPair } from "../types";
import { apiFetch } from "../services/api";

export function useQA() {
  const [qaInput, setQaInput] = useState("");
  const [qaHistory, setQaHistory] = useState<QAPair[]>([]);

  const resetQA = useCallback(() => {
    setQaInput("");
    setQaHistory([]);
  }, []);

  const askQA = useCallback(async (
    context: string,
    deps: {
      setError: (e: string | null) => void;
      setLoading: (v: boolean) => void;
      onAnswered: (newHistory: QAPair[]) => Promise<void>;
    },
  ) => {
    if (!qaInput.trim()) return;
    if (!context) {
      alert("⚠️ กรุณาอัปโหลดไฟล์ PDF หรือพิมพ์เนื้อหาในกล่องข้อความก่อนเริ่มถามครับ");
      return;
    }

    const currentQ = qaInput;
    deps.setLoading(true);
    setQaInput("");

    try {
      const raw = await apiFetch<unknown>("/qa", {
        method: "POST",
        json: { context, question: currentQ },
      });
      const json = parseApi(QAResponseSchema, raw, "qa");
      const finalAns = json.answer;

      // อ่านค่า source (ช่วงหน้าที่ AI ใช้ตอบ) จาก response ตรง ๆ
      // ไม่ผ่าน schema เพื่อไม่ต้องแก้ schemas/api.ts
      const source =
        raw && typeof raw === "object" && "source" in raw &&
          typeof (raw as { source?: unknown }).source === "string"
          ? ((raw as { source: string }).source)
          : "";

      const newHistory = [{ question: currentQ, answer: finalAns, source }, ...qaHistory];
      setQaHistory(newHistory);
      await deps.onAnswered(newHistory);
    } catch (e) {
      deps.setError(e instanceof Error ? e.message : String(e));
      setQaInput(currentQ);
    } finally {
      deps.setLoading(false);
    }
  }, [qaInput, qaHistory]);

  return { qaInput, setQaInput, qaHistory, setQaHistory, resetQA, askQA };
}