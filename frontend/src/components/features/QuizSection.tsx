import type { QuizItem } from "../../types";
import { idxToLetter } from "../../utils/helpers";
import { Card } from "../ui/Card";
import { PrimaryBtn } from "../ui/PrimaryBtn";

type Props = {
  questions: QuizItem[];
  answers: Record<number, string>;
  score: number | null;
  lockedCount: number;
  isOverallSubmitted: boolean;
  isAllAnswered: boolean;
  showSaveButton: boolean;
  onAnswerChange: (idx: number, val: string) => void;
  onSubmit: () => void;
  onSaveQuestion: (idx: number) => void;
};

export function QuizSection({
  questions,
  answers,
  score,
  lockedCount,
  isOverallSubmitted,
  isAllAnswered,
  showSaveButton,
  onAnswerChange,
  onSubmit,
  onSaveQuestion,
}: Props) {
  if (questions.length === 0) return null;

  return (
    <Card>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold flex items-center gap-2">แบบทดสอบ</h2>
        <span className="text-xs bg-zinc-800 px-3 py-1 rounded-full text-zinc-400">{questions.length} ข้อ</span>
      </div>
      <ol className="space-y-4">
        {questions.map((q, idx) => {
          const isThisQuestionSubmitted = isOverallSubmitted || idx < lockedCount;
          const selectedLetter = answers[idx];
          const hasSelected = !!selectedLetter;
          const isCorrect = hasSelected && String(selectedLetter).toLowerCase() === String(q.answer).toLowerCase();
          const headDotColor = hasSelected
            ? isThisQuestionSubmitted
              ? isCorrect ? "bg-emerald-400" : "bg-red-400"
              : "bg-zinc-500"
            : "bg-zinc-800";

          return (
            <li key={idx} className="rounded-2xl border border-zinc-800 bg-zinc-900/30 p-5 hover:border-zinc-700 transition">
              <div className="mb-4 font-medium flex flex-col md:flex-row md:items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1">
                  <span aria-hidden className={`shrink-0 inline-block h-2.5 w-2.5 rounded-full mt-1.5 ${headDotColor}`} />
                  <span className="leading-snug text-zinc-100 text-lg">{idx + 1}. {q.question}</span>
                </div>
                <div className="flex flex-wrap items-center gap-2 md:self-start shrink-0">
                  {hasSelected && (
                    <span className="text-xs px-2 py-1 rounded bg-zinc-800 text-zinc-300">
                      เลือก: <b>{String(selectedLetter).toUpperCase()}</b>
                    </span>
                  )}
                  {showSaveButton && (
                    <button
                      className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/40 transition border border-indigo-500/30"
                      onClick={() => onSaveQuestion(idx)}
                    >
                      บันทึก
                    </button>
                  )}
                </div>
              </div>

              {q.type === "mcq" ? (
                <div className="grid gap-2 pl-5">
                  {q.choices?.map((c, i) => {
                    const letter = idxToLetter[i];
                    const selected = answers[idx] === letter;
                    const isCorrectChoice = letter === q.answer;
                    const wrongSelected = isThisQuestionSubmitted && selected && !isCorrectChoice;
                    let cls = "flex items-center gap-3 rounded-xl border px-4 py-3 cursor-pointer transition ";
                    if (!isThisQuestionSubmitted) cls += selected ? "border-indigo-500 bg-indigo-500/10" : "border-zinc-800 hover:bg-zinc-800 hover:border-zinc-600";
                    else cls += isCorrectChoice ? "border-emerald-500 bg-emerald-500/10" : wrongSelected ? "border-red-500 bg-red-500/10" : "border-zinc-800 opacity-60";

                    return (
                      <label key={i} className={cls}>
                        <input
                          type="radio"
                          name={`q-${idx}`}
                          value={letter}
                          checked={selected}
                          disabled={isThisQuestionSubmitted}
                          className="sr-only"
                          onChange={(e) => onAnswerChange(idx, e.target.value)}
                        />
                        <div className={`w-6 h-6 rounded-full border flex items-center justify-center text-xs mr-2 transition ${selected ? "border-indigo-400 text-indigo-400" : "border-zinc-600 text-zinc-500"}`}>
                          {letter}
                        </div>
                        <span className="text-zinc-300">{c}</span>
                      </label>
                    );
                  })}
                </div>
              ) : (
                <div className="flex gap-3 pl-5">
                  {["true", "false"].map((v) => {
                    const selected = answers[idx] === v;
                    const isCorrectChoice = q.answer.toLowerCase() === v;
                    const wrongSelected = isThisQuestionSubmitted && selected && !isCorrectChoice;
                    let cls = "flex-1 flex items-center justify-center gap-3 rounded-xl border px-4 py-3 cursor-pointer transition ";
                    if (!isThisQuestionSubmitted) cls += selected ? "border-indigo-500 bg-indigo-500/10" : "border-zinc-800 hover:bg-zinc-800";
                    else cls += isCorrectChoice ? "border-emerald-500 bg-emerald-500/10" : wrongSelected ? "border-red-500 bg-red-500/10" : "border-zinc-800 opacity-60";

                    return (
                      <label key={v} className={cls}>
                        <input
                          type="radio"
                          name={`q-${idx}`}
                          value={v}
                          checked={selected}
                          disabled={isThisQuestionSubmitted}
                          className="sr-only"
                          onChange={(e) => onAnswerChange(idx, e.target.value)}
                        />
                        <span className={selected ? "font-semibold text-white" : "text-zinc-400"}>
                          {v === "true" ? "จริง (True)" : "เท็จ (False)"}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}

              {isThisQuestionSubmitted && (
                <div className="mt-4 p-4 rounded-xl bg-zinc-950 border border-zinc-800 text-sm ml-5">
                  <div className="text-emerald-400 font-semibold mb-1">เฉลย: {String(q.answer).toUpperCase()}</div>
                  {q.explain && <div className="text-zinc-400">{q.explain}</div>}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <div className="mt-8 pt-6 border-t border-zinc-800 flex items-center justify-between">
        <div className="text-xs text-zinc-500">
          {isAllAnswered
            ? "* กดเพื่อตรวจคะแนน"
            : `* กรุณาตอบให้ครบทุกข้อ (${Object.keys(answers).length} / ${questions.length})`}
        </div>
        <PrimaryBtn
          onClick={onSubmit}
          disabled={isOverallSubmitted || !isAllAnswered}
          className={`px-8 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 ${!isAllAnswered && !isOverallSubmitted ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          ตรวจคะแนน
        </PrimaryBtn>
      </div>

      {isOverallSubmitted && score !== null && (
        <div className="mt-8 text-center p-8 rounded-3xl bg-zinc-900/40 border border-zinc-800/80 shadow-2xl backdrop-blur-sm animate-in zoom-in-95 duration-500">
          <div className="text-zinc-400 text-sm font-bold tracking-widest mb-2">คะแนนของคุณ</div>
          <div className="flex items-baseline justify-center gap-2">
            <span className="text-6xl font-black bg-gradient-to-tr from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              {score}
            </span>
            <span className="text-3xl font-bold text-zinc-600">/ {questions.length}</span>
          </div>
        </div>
      )}
    </Card>
  );
}
