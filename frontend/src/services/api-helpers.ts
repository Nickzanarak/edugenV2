import { QuizItem } from "../types";
import { hasArrayQuestions, isStringArray, stripChoiceLabel, toStr, idxToLetter, letterToIdx, shuffle } from "../utils/helpers";

export { getAPIBase } from "./api";

export function normalizeFromAPI(payload: unknown, choicesCount = 4): QuizItem[] {
  const cc = Math.max(4, Math.min(6, choicesCount));
  const validLetters = idxToLetter.slice(0, cc);
  const raw: unknown[] = hasArrayQuestions(payload) ? payload.questions : [];
  const out: QuizItem[] = [];

  for (const item of raw) {
    if (typeof item !== "object" || item === null) continue;
    const q = item as Record<string, unknown>;
    const type = toStr(q.type).toLowerCase();
    const question = toStr(q.question);
    let answer = toStr(q.answer).toLowerCase();
    const explain = q.explain !== undefined ? toStr(q.explain) : undefined;

    if (!type || !question) continue;

    if (type === "mcq") {
      const choicesRaw = isStringArray(q.choices) ? q.choices : [];
      const mapped = choicesRaw.map(stripChoiceLabel).filter(Boolean).slice(0, cc);
      const need = Math.max(0, cc - mapped.length);
      const choices: string[] = need > 0 ? [...mapped, ...Array.from({ length: need }, (_, i) => `ตัวเลือกที่ ${mapped.length + i + 1}`)] : mapped;

      if (!validLetters.includes(answer)) {
        const num = Number(answer);
        if (Number.isFinite(num)) {
          const idx = num >= 1 && num <= cc ? num - 1 : num;
          if (idx >= 0 && idx < cc) answer = idxToLetter[idx];
        }
        if (!validLetters.includes(answer)) {
          const idx = choices.findIndex((c) => c.replace(/\s+/g, "") === answer.replace(/\s+/g, ""));
          answer = idx >= 0 ? idxToLetter[idx] : "ก";
        }
      }
      out.push({ type: "mcq", question, choices, answer, explain });
      continue;
    }

    if (!["true", "false"].includes(answer)) {
      const trueSet = new Set(["true", "t", "1", "yes", "y", "จริง", "ถูก"]);
      const falseSet = new Set(["false", "f", "0", "no", "n", "เท็จ", "ผิด"]);
      if (trueSet.has(answer)) answer = "true";
      else if (falseSet.has(answer)) answer = "false";
      else answer = "false";
    }
    out.push({ type: "tf", question, answer, explain });
  }
  return out;
}

export function shuffleAndRemapBatch(qs: QuizItem[]): QuizItem[] {
  return shuffle(qs).map((q) => {
    if (q.type !== "mcq" || !q.choices?.length) return q;
    const original = [...q.choices];
    const correctIdx = letterToIdx[q.answer] ?? -1;
    const correctText = correctIdx >= 0 && correctIdx < original.length ? original[correctIdx] : null;
    const newChoices = shuffle(original);
    let newAns = q.answer;

    if (correctText) {
      const newIdx = newChoices.findIndex((t) => t === correctText);
      if (newIdx >= 0) newAns = idxToLetter[newIdx] || newAns;
    }
    return { ...q, choices: newChoices, answer: newAns };
  });
}