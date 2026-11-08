import { useCallback, useState } from "react";
import { parseApi } from "../lib/validate";
import { QAResponseSchema } from "../schemas/api";
import type { QAPair } from "../types";
import { apiFetch, type AuthHeaders } from "../services/api";

export function useQA(authHeader: AuthHeaders) {
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
      /** แจ้งเตือนผู้ใช้ (ใช้ Toast แทน alert ของเบราว์เซอร์) */
      onNotice?: (msg: string) => void;
    },
  ) => {

    //เช็คก่อนส่ง
    if (!qaInput.trim()) return;  // ถ้าไม่ได้พิมพ์คำถาม จะ หยุด
    if (!context) {               // ถ้ายังไม่มีเอกสาร เตือน แล้วหยุด
      deps.onNotice?.("กรุณาอัปโหลดไฟล์ PDF หรือพิมพ์เนื้อหาก่อนเริ่มถาม");
      return;
    }

    //ตอนเตรียมตัว
    const currentQ = qaInput; // จำคำถามไว้
    deps.setLoading(true);    // เปิดสถานะกำลังโหลด
    setQaInput("");           // ล้างช่องพิมพ์ทันที

    //ส่งไปหลังบ้าน
    try {
      const raw = await apiFetch<unknown>("/qa", {
        method: "POST",
        auth: authHeader, // บัตรผ่าน
        json: { context, question: currentQ }, // เนื้อหาทั้งเล่ม + คำถาม
      });

      //ได้คำตอบกลับมาจาก Backend แล้ว
      const json = parseApi(QAResponseSchema, raw, "qa"); // ตรวจช่อง answer
      const finalAns = json.answer; // หยิบข้อความคำตอบออกมา ไว้แสดงบนหน้าจอและบันทึกลงประวัติ

      // อ่านค่า source (ช่วงหน้าที่ AI ใช้ตอบ) จาก response ตรง ๆ
      // ไม่ผ่าน schema เพื่อไม่ต้องแก้ schemas/api.ts
      const source =
        raw && typeof raw === "object" && "source" in raw &&
          typeof (raw as { source?: unknown }).source === "string"
          ? ((raw as { source: string }).source)
          : "";

      //เพิ่มลงรายการถาม-ตอบ
      const newHistory = [{ question: currentQ, answer: finalAns, source }, ...qaHistory]; // ของใหม่อยู่บนสุด
      setQaHistory(newHistory); //เปลี่ยนกล่อง  React วาดหน้าจอใหม่
      await deps.onAnswered(newHistory);
    } catch (e) {
      deps.setError(e instanceof Error ? e.message : String(e));
      setQaInput(currentQ);
    } finally {
      deps.setLoading(false);
    }
  }, [qaInput, qaHistory, authHeader]);

  return { qaInput, setQaInput, qaHistory, setQaHistory, resetQA, askQA };
}