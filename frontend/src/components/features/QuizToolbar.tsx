import { useState } from "react";
import { MAX_QUESTIONS } from "../../constants/quiz";
import { QuizConfigModal } from "./QuizConfigModal";
import type { QuizConfig } from "../../hooks/useQuiz";

type Props = {
  mcqCount: number;
  tfCount: number;
  loading: boolean;
  topicCount: number;
  onAdd: (type: "mcq" | "tf", config: QuizConfig) => void;
};

export function QuizToolbar({ mcqCount, tfCount, loading, topicCount, onAdd }: Props) {
  const [openType, setOpenType] = useState<"mcq" | "tf" | null>(null);

  const currentCount = openType === "mcq" ? mcqCount : tfCount;
  const maxCount = MAX_QUESTIONS - currentCount;

  const handleConfirm = (config: QuizConfig) => {
    if (!openType) return;
    onAdd(openType, config);
    setOpenType(null);
  };

  return (
    <>
      <button
        onClick={() => setOpenType("mcq")}
        disabled={loading || mcqCount >= MAX_QUESTIONS}
        className="group flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all duration-300 disabled:opacity-50 bg-sky-900/20 border border-sky-500/30 text-sky-400 hover:bg-sky-500/20 hover:text-sky-300 flex-1 sm:flex-none whitespace-nowrap"
      >
        <span>+ ปรนัย</span>
        <span className="bg-sky-950/60 px-1.5 py-0.5 rounded text-xs border border-sky-500/20 group-hover:border-sky-400/40">
          {mcqCount}/{MAX_QUESTIONS}
        </span>
      </button>

      <button
        onClick={() => setOpenType("tf")}
        disabled={loading || tfCount >= MAX_QUESTIONS}
        className="group flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all duration-300 disabled:opacity-50 bg-emerald-900/20 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 hover:text-emerald-300 flex-1 sm:flex-none whitespace-nowrap"
      >
        <span>+ ถูกผิด</span>
        <span className="bg-emerald-950/60 px-1.5 py-0.5 rounded text-xs border border-emerald-500/20 group-hover:border-emerald-400/40">
          {tfCount}/{MAX_QUESTIONS}
        </span>
      </button>

      {openType && (
        <QuizConfigModal
          open={!!openType}
          type={openType}
          maxCount={maxCount}
          topicCount={topicCount}
          onClose={() => setOpenType(null)}
          onConfirm={handleConfirm}
        />
      )}
    </>
  );
}