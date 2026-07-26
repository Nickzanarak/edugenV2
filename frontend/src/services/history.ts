import { parseApi } from "../lib/validate";
import { HistoryListSchema } from "../schemas/api";
import type { AuthHeaders } from "./api";
import { apiFetch } from "./api";
import type { DataPoint, HistoryItem, QAPair, QuizItem, Section } from "../types";

export type HistorySaveInput = {
  pdf: File | null;
  currentHistoryId: string | null;
  historyItems: HistoryItem[];
  fileId: string;
  overview: string;
  keyPoints: string[];
  sections: Section[];
  dataPoints: DataPoint[];
  questions: QuizItem[];
  answers: Record<number, string>;
  score: number;
  content: string;
  qaHistory: QAPair[];
  manualFallback?: string;
};

export function resolveHistoryFileName(input: Pick<
  HistorySaveInput,
  "pdf" | "currentHistoryId" | "historyItems" | "fileId" | "manualFallback"
>): string {
  if (input.pdf) return input.pdf.name;
  if (input.currentHistoryId) {
    const item = input.historyItems.find((h) => h.id === input.currentHistoryId);
    return item ? item.fileName : input.fileId;
  }
  if (input.fileId === "manual") {
    return input.manualFallback ?? `สรุปเนื้อหา ${new Date().toLocaleTimeString("th-TH")}`;
  }
  return input.fileId;
}

export function buildHistoryPayload(input: HistorySaveInput) {
  return {
    file_name: resolveHistoryFileName(input),
    overview: input.overview || "",
    key_points: input.keyPoints,
    sections: input.sections,
    data_points: input.dataPoints,
    questions: input.questions,
    answers: input.answers,
    score: input.score,
    content: input.content,
    qa_history: input.qaHistory,
  };
}

export async function saveOrUpdateHistory(
  auth: AuthHeaders,
  currentHistoryId: string | null,
  payload: ReturnType<typeof buildHistoryPayload>,
): Promise<{ id: string } | null> {
  if (currentHistoryId) {
    await apiFetch(`/history/update/${currentHistoryId}`, {
      method: "PATCH",
      auth,
      json: payload,
    });
    return null;
  }

  const saved = await apiFetch<{ id?: string }>("/history/save", {
    method: "POST",
    auth,
    json: payload,
  });
  return saved.id ? { id: saved.id } : null;
}

export async function fetchHistoryList(auth: AuthHeaders): Promise<HistoryItem[]> {
  const data = await apiFetch<unknown>("/history/list", { auth });
  return parseApi(HistoryListSchema, data, "history list") as HistoryItem[];
}

export async function deleteHistoryItem(auth: AuthHeaders, id: string): Promise<void> {
  await apiFetch(`/history/${id}`, { method: "DELETE", auth });
}

export async function renameHistoryItem(auth: AuthHeaders, id: string, newName: string): Promise<void> {
  await apiFetch(`/history/${id}`, {
    method: "PATCH",
    auth,
    json: { new_name: newName },
  });
}
