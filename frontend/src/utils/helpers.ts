import { QuizItem } from "../types";

export function hasArrayQuestions(x: unknown): x is { questions: unknown[] } {
  if (typeof x !== "object" || x === null) return false;
  const q = (x as { questions?: unknown }).questions;
  return Array.isArray(q);
}

export function hasDetail(x: unknown): x is { detail?: string } {
  return typeof x === "object" && x !== null && "detail" in x;
}

export function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === "string");
}

export const idxToLetter = ["ก", "ข", "ค", "ง", "จ", "ฉ"];
export const letterToIdx: Record<string, number> = { ก: 0, ข: 1, ค: 2, ง: 3, จ: 4, ฉ: 5 };

export const stripChoiceLabel = (s: string) => String(s).replace(/^\s*[กขคงจฉ]\)\s*/i, "").trim();

export const toStr = (v: unknown) => (typeof v === "string" ? v : String(v ?? "")).trim();

export function shuffle<T>(arr: T[]) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export const keyFor = (q: QuizItem) =>
  q.question.normalize("NFKC").replace(/\s+/g, " ").replace(/[^\p{L}\p{N}\s]/gu, "").trim().toLowerCase();