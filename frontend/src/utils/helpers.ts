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

// ตัดตัวอักษรนำหน้าตัวเลือกออก เช่น "ก) ...", "ก. ...", "ก . ..."
// ต้องมีตัวคั่น ) หรือ . เสมอ เพื่อไม่ให้ไปตัดคำไทยที่ขึ้นต้นด้วย ก ข ค ง จ ฉ
// (เช่น "การประมวลผล", "ความปลอดภัย", "งานวิจัย")
export const stripChoiceLabel = (s: string) => String(s).replace(/^\s*[กขคงจฉ]\s*[).]\s*/, "").trim();

export const toStr = (v: unknown) => (typeof v === "string" ? v : String(v ?? "")).trim();

export function shuffle<T>(arr: T[]) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}