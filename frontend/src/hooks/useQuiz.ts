import { useCallback, useRef, useState, type Dispatch, type SetStateAction } from "react";
import type { HistoryItem, QuizItem } from "../types";
import { normalizeFromAPI, shuffleAndRemapBatch } from "../services/api-helpers";
import { apiFetch, type AuthHeaders } from "../services/api";
import { parseApi } from "../lib/validate";
import { QuizApiResponseSchema, TopicsResponseSchema } from "../schemas/api";
import { MAX_QUESTIONS } from "../constants/quiz";

export type QuizConfig = {
  count: number;
  difficulty: string;
  choicesCount: number;
};

export function useQuiz(context: string, authHeader: AuthHeaders) {
  const [questions, setQuestions] = useState<QuizItem[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [score, setScore] = useState<number | null>(null);
  const [lockedCount, setLockedCount] = useState(0);
  const topicsRef = useRef<string[]>([]);

  const countByType = useCallback(
    (t: "mcq" | "tf") => questions.filter((q) => q.type === t).length,
    [questions],
  );

  const resetQuiz = useCallback(() => {
    setScore(null);
    setQuestions([]);
    setAnswers({});
    topicsRef.current = [];
    setLockedCount(0);
  }, []);

  const restoreFromHistory = useCallback((item: {
    questions?: QuizItem[];
    answers?: Record<string, string>;
    score: number;
    lockedCount?: number;
  }) => {
    if (item.questions && item.questions.length > 0) {
      setQuestions(item.questions);
      setAnswers(item.answers as Record<number, string>);
      if (item.score < 0) {
        setScore(null);
        setLockedCount(item.lockedCount || 0);
      } else {
        setScore(item.score);
        setLockedCount(item.lockedCount !== undefined ? item.lockedCount : item.questions.length);
      }
    } else {
      setQuestions([]);
      setScore(null);
      setLockedCount(0);
      setAnswers({});
    }
    topicsRef.current = [];
  }, []);

  /** โหลดหัวข้อจากเนื้อหา
   *  รับ overrideContext ได้ สำหรับกรณีที่เพิ่ง setState แล้ว state ยังไม่อัปเดต
   *  (React เปลี่ยนค่า state แบบ async — ถ้าพึ่ง context จาก closure จะได้ค่าเก่า)
   */
  const ensureTopics = useCallback(async (overrideContext?: string) => {
    const ctx = (overrideContext ?? context) || "";
    if (!ctx || topicsRef.current.length >= 10) return;
    try {
      const raw = await apiFetch<unknown>("/quiz/topics", {
        method: "POST",
        auth: authHeader,
        json: { context: ctx },
      });
      const json = parseApi(TopicsResponseSchema, raw, "quiz topics");
      if (json.topics.length > 0) {
        const exist = new Set(topicsRef.current.map((t) => t.toLowerCase()));
        for (const t of json.topics) {
          const k = String(t).trim().toLowerCase();
          if (k && !exist.has(k)) {
            topicsRef.current.push(t);
            exist.add(k);
          }
        }
      }
    } catch { /* optional */ }
  }, [context, authHeader]);

  const addMoreQuiz = useCallback(async (
    type: "mcq" | "tf",
    config: QuizConfig,
    deps: {
      setError: (e: string | null) => void;
      setLoading: (v: boolean) => void;
      setLoadingText: (t: string) => void;
      onUpdated: (newQuestions: QuizItem[]) => Promise<void>;
    },
  ) => {
    if (!context) return;
    deps.setError(null);
    const already = questions.filter((q) => q.type === type).length;
    const remain = MAX_QUESTIONS - already;
    if (remain <= 0) return;

    const want = Math.min(config.count, remain);
    deps.setLoading(true);
    deps.setLoadingText(`กำลังสร้างข้อสอบ ${type === "mcq" ? "แบบปรนัย " : "แบบถูกผิด "} เพิ่ม`);

    await ensureTopics();
    // ยังไม่ตัดหัวข้อออกตอนนี้ รอจนสร้างข้อสอบสำเร็จก่อน
    // (เดิมใช้ splice ทันที ทำให้หัวข้อหายถาวรถ้า API ล้มเหลว)
    const topicSlice = topicsRef.current.slice(0, want);

    try {
      const excludeTexts = questions
        .filter((q) => q.type === type)
        .map((q) => q.question);

      const raw = await apiFetch<unknown>(`/quiz/${type}`, {
        method: "POST",
        auth: authHeader,
        json: {
          context,
          n: want,
          exclude: excludeTexts,
          topics: topicSlice.length ? topicSlice : undefined,
          difficulty: config.difficulty,
          choices_count: type === "mcq" ? config.choicesCount : undefined,
        },
      });
      const json = parseApi(QuizApiResponseSchema, raw, `quiz ${type}`);
      const incoming = normalizeFromAPI(json, config.choicesCount).filter((q) => q.type === type);

      if (incoming.length === 0) {
        deps.setError(`ไม่พบข้อใหม่ ${type}`);
        return;
      }

      // สำเร็จแล้วค่อยตัดหัวข้อที่ใช้ไปออกจากคิว
      topicsRef.current.splice(0, want);
      const batchReady = shuffleAndRemapBatch(incoming.slice(0, want));
      const newQuestions = [...questions, ...batchReady];
      setQuestions(newQuestions);
      setScore(null);
      await deps.onUpdated(newQuestions);
    } catch (e) {
      deps.setError(e instanceof Error ? e.message : String(e));
    } finally {
      deps.setLoading(false);
      deps.setLoadingText("");
    }
  }, [context, ensureTopics, questions, authHeader]);

  const submitQuiz = useCallback(async (onSubmitted: (correct: number) => Promise<void>) => {
    let correct = 0;
    questions.forEach((q, i) => {
      const u = (answers[i] || "").toLowerCase();
      if (u === String(q.answer).toLowerCase()) correct++;
    });
    setScore(correct);
    setLockedCount(questions.length);
    await onSubmitted(correct);
  }, [questions, answers]);

  const handleAnswerChange = useCallback((
    idx: number,
    val: string,
    currentHistoryId: string | null,
    setHistoryItems: Dispatch<SetStateAction<HistoryItem[]>>,
  ) => {
    setAnswers((prev) => {
      const newAns = { ...prev, [idx]: val };
      if (currentHistoryId) {
        setHistoryItems((items) =>
          items.map((item) => (item.id === currentHistoryId ? { ...item, answers: newAns } : item)),
        );
      }
      return newAns;
    });
  }, []);

  return {
    questions,
    setQuestions,
    answers,
    setAnswers,
    score,
    setScore,
    lockedCount,
    setLockedCount,
    topicsRef,
    countByType,
    resetQuiz,
    restoreFromHistory,
    ensureTopics,
    addMoreQuiz,
    submitQuiz,
    handleAnswerChange,
    isOverallSubmitted: score !== null,
    isAllAnswered: questions.length > 0 && Object.keys(answers).length === questions.length,
  };
}