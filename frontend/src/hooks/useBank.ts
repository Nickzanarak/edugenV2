import { useCallback, useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { parseApi } from "../lib/validate";
import { BankQuestionSchema, BankQuestionListSchema, QuizSetListSchema } from "../schemas/api";
import type { AuthHeaders } from "../services/api";
import { apiFetch, apiFetchBlob, ApiError } from "../services/api";
import type { BankQuestion, QuizItem, QuizSet } from "../types";

function bankAuthKey(authHeader: AuthHeaders): string {
  return authHeader.Authorization ?? authHeader["X-User-Id"] ?? "";
}

function pickFilenameFromHeader(h: Headers): string | null {
  const disp = h.get("Content-Disposition") || h.get("content-disposition");
  if (!disp) return null;
  const m = /filename\*?=(?:UTF-8''|")?([^\";]+)\"?/i.exec(disp);
  if (m && m[1]) {
    try { return decodeURIComponent(m[1]); } catch { return m[1]; }
  }
  return null;
}

/** แปลข้อผิดพลาดตอนส่งออก PDF เป็นข้อความที่บอกสาเหตุได้จริง
 *  (เดิมแสดง "เช็ก API/CORS" เหมือนกันหมด ผู้ใช้ไม่รู้ว่าต้องแก้อะไร) */
function describeExportError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return "ต้องเข้าสู่ระบบก่อนจึงจะส่งออกได้";
    if (e.status === 404) return "ไม่พบชุดข้อสอบนี้ อาจถูกลบไปแล้ว";
    if (e.status === 400) return "ชุดนี้ยังไม่มีข้อสอบ กรุณาเพิ่มข้อสอบก่อนส่งออก";
    if (e.status >= 500) return "เซิร์ฟเวอร์มีปัญหาในการสร้างไฟล์ กรุณาลองใหม่";
    return `ส่งออกไม่สำเร็จ (รหัส ${e.status})`;
  }
  return "ส่งออกไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่อแล้วลองใหม่";
}

function buildQuestionPayload(q: QuizItem | BankQuestion) {
  const isMcq = q.type === "mcq";
  if (isMcq) {
    return {
      type: "mcq" as const,
      question: q.question,
      choices: (q.choices ?? []).slice(0, 6),
      answer: q.answer,
      explain: q.explain || "",
    };
  }
  return {
    type: "tf" as const,
    question: q.question,
    answer: String(q.answer).toLowerCase() === "true" ? "true" : "false",
    explain: q.explain || "",
  };
}

export function useBank(authHeader: AuthHeaders) {
  const authKey = bankAuthKey(authHeader);
  const queryClient = useQueryClient();

  const [setsOpen, setSetsOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState<{ open: boolean; qIndex: number | null }>({ open: false, qIndex: null });
  const [creatingTitle, setCreatingTitle] = useState("");
  const [manualOpen, setManualOpen] = useState(false);
  const [manualSetId, setManualSetId] = useState<number | null>(null);
  const [manualType, setManualType] = useState<"mcq" | "tf">("mcq");
  const [manualQ, setManualQ] = useState("");
  const [manualChoices, setManualChoices] = useState<string[]>(["", "", "", ""]);
  const [manualAns, setManualAns] = useState<string>("ก");
  const [manualExplain, setManualExplain] = useState("");
  const [editOpen, setEditOpen] = useState<{ open: boolean; set: QuizSet | null }>({ open: false, set: null });

  const needsBankData = setsOpen || saveOpen.open || editOpen.open || manualOpen;

  const setsQuery = useQuery({
    queryKey: ["bank", "quizzes", authKey],
    queryFn: async () => {
      const raw = await apiFetch<unknown>("/bank/quizzes", { auth: authHeader });
      return parseApi(QuizSetListSchema, raw, "bank quizzes");
    },
    enabled: !!authKey && needsBankData,
  });

  const bankQuery = useQuery({
    queryKey: ["bank", "questions", authKey],
    queryFn: async () => {
      const raw = await apiFetch<unknown>("/bank/questions", { auth: authHeader });
      return parseApi(BankQuestionListSchema, raw, "bank questions");
    },
    enabled: !!authKey && needsBankData,
  });

  const sets = useMemo(() => setsQuery.data ?? [], [setsQuery.data]);
  const bankQuestions = useMemo(() => bankQuery.data ?? [], [bankQuery.data]);

  const invalidateBank = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["bank", "quizzes", authKey] });
    queryClient.invalidateQueries({ queryKey: ["bank", "questions", authKey] });
  }, [queryClient, authKey]);

  const createSetMutation = useMutation({
    mutationFn: (title: string) =>
      apiFetch("/bank/quizzes", { method: "POST", auth: authHeader, json: { title, question_ids: [] } }),
    onSuccess: invalidateBank,
  });

  const renameSetMutation = useMutation({
    mutationFn: ({ id, title, ids }: { id: number; title: string; ids?: number[] }) =>
      apiFetch(`/bank/quizzes/${id}`, { method: "PATCH", auth: authHeader, json: { title, question_ids: ids } }),
    onSuccess: invalidateBank,
  });

  const deleteSetMutation = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/bank/quizzes/${id}`, { method: "DELETE", auth: authHeader }),
    onSuccess: invalidateBank,
  });

  const saveQuestionMutation = useMutation({
    mutationFn: async ({ setId, q }: { setId: number; q: QuizItem }) => {
      const raw = await apiFetch<unknown>(`/bank/quizzes/${setId}/questions`, {
        method: "POST",
        auth: authHeader,
        json: buildQuestionPayload(q),
      });
      return parseApi(BankQuestionSchema, raw, "bank question");
    },
    onSuccess: invalidateBank,
  });

  const updateQuestionMutation = useMutation({
    mutationFn: (q: BankQuestion) =>
      apiFetch(`/bank/questions/${q.id}`, { method: "PATCH", auth: authHeader, json: buildQuestionPayload(q) }),
    onSuccess: invalidateBank,
  });

  const loadSets = useCallback(async () => {
    await setsQuery.refetch();
  }, [setsQuery]);

  const loadBank = useCallback(async () => {
    await bankQuery.refetch();
  }, [bankQuery]);

  const openLibrary = useCallback(() => {
    setSetsOpen(true);
  }, []);

  const createSet = useCallback(
    (title: string) => createSetMutation.mutateAsync(title),
    [createSetMutation],
  );

  const renameSet = useCallback(
    (id: number, title: string, ids?: number[]) =>
      renameSetMutation.mutateAsync({ id, title, ids }),
    [renameSetMutation],
  );

  const deleteSet = useCallback(
    (id: number) => deleteSetMutation.mutateAsync(id),
    [deleteSetMutation],
  );

  const exportSetPdf = useCallback(async (
    id: number,
    onError: (msg: string) => void,
    opts = { showAnswers: false },
  ) => {
    try {
      const r = await apiFetchBlob(`/export/quizzes/${id}`, { method: "POST", auth: authHeader, json: opts });
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const byHeader = pickFilenameFromHeader(r.headers);
      const byTitle = sets.find((s) => s.id === id)?.title || `quiz-${id}`;
      a.href = url;
      a.download = byHeader && byHeader.endsWith(".pdf") ? byHeader : `${byTitle}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // หน่วงก่อนคืนหน่วยความจำ เพราะบางเบราว์เซอร์ยังอ่านไฟล์ไม่เสร็จ
      // ถ้าคืนทันทีอาจได้ไฟล์ที่ดาวน์โหลดไม่สมบูรณ์
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      onError(describeExportError(e));
    }
  }, [authHeader, sets]);

  const saveQuestionToSet = useCallback(
    (setId: number, q: QuizItem) => saveQuestionMutation.mutateAsync({ setId, q }),
    [saveQuestionMutation],
  );

  const openSaveQuestion = useCallback((qIndex: number) => {
    setSaveOpen({ open: true, qIndex });
  }, []);

  const updateBankQuestion = useCallback(
    (q: BankQuestion) => updateQuestionMutation.mutateAsync(q),
    [updateQuestionMutation],
  );

  return {
    setsOpen, setSetsOpen,
    sets,
    saveOpen, setSaveOpen,
    creatingTitle, setCreatingTitle,
    manualOpen, setManualOpen,
    manualSetId, setManualSetId,
    manualType, setManualType,
    manualQ, setManualQ,
    manualChoices, setManualChoices,
    manualAns, setManualAns,
    manualExplain, setManualExplain,
    editOpen, setEditOpen,
    bankQuestions,
    loadSets, loadBank, openLibrary,
    createSet, renameSet, deleteSet,
    exportSetPdf, saveQuestionToSet, openSaveQuestion, updateBankQuestion,
  };
}