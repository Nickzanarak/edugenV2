import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

type Props = {
    open: boolean;
    type: "mcq" | "tf";
    maxCount: number;
    topicCount: number;
    onClose: () => void;
    onConfirm: (config: { count: number; difficulty: string; choicesCount: number }) => void;
};

function LevelIcon({ level, active }: { level: number; active: boolean }) {
    return (
        <div className="flex items-end justify-center gap-[3px] h-4">
            {[1, 2, 3].map((lv) => (
                <div
                    key={lv}
                    style={{ height: `${lv * 33}%` }}
                    className={`w-[3px] rounded-full transition-colors ${lv <= level
                            ? active ? "bg-indigo-300" : "bg-zinc-400"
                            : active ? "bg-indigo-300/25" : "bg-zinc-700"
                        }`}
                />
            ))}
        </div>
    );
}

const DIFFICULTIES = [
    { value: "easy", label: "ง่าย", desc: "เน้นความจำและทบทวน", level: 1 },
    { value: "medium", label: "ปานกลาง", desc: "ผสมผสานประยุกต์ความเข้าใจ", level: 2 },
    { value: "hard", label: "ยาก", desc: "ต้องคิดวิเคราะห์", level: 3 },
];

const TYPE_LABEL = {
    mcq: "ข้อสอบปรนัย",
    tf: "ข้อสอบถูก / ผิด",
};

export function QuizConfigModal({
    open,
    type,
    maxCount,
    topicCount,
    onClose,
    onConfirm,
}: Props) {
    const [count, setCount] = useState(5);
    const [difficulty, setDifficulty] = useState("medium");
    const [choicesCount, setChoicesCount] = useState(4);

    useEffect(() => {
        if (open) {
            setCount(Math.min(5, maxCount));
            setDifficulty("medium");
            setChoicesCount(4);
        }
    }, [open, maxCount]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    if (!open) return null;

    const clamp = (v: number) => Math.max(1, Math.min(maxCount, v));
    const isOverTopics = topicCount > 0 && count > topicCount;
    const presets = [3, 5, 10, 15].filter((p) => p <= maxCount);

    return createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
                className="absolute inset-0 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200"
                onClick={onClose}
            />

            <div className="relative w-full max-w-lg rounded-3xl border border-zinc-800/70 bg-[#111113] shadow-2xl shadow-black/80 animate-in zoom-in-95 fade-in duration-200">
                <div className="px-7 pt-7 pb-6">
                    <button
                        onClick={onClose}
                        className="absolute right-5 top-5 p-1.5 rounded-lg text-zinc-500 hover:bg-zinc-800/70 hover:text-zinc-200 transition-colors"
                        aria-label="ปิด"
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>

                    <h2 className="text-xl font-bold text-zinc-50">การตั้งค่าแบบทดสอบ</h2>
                    <p className="mt-1 text-[13px] text-zinc-500">
                        ปรับแต่งความยากและจำนวนข้อสำหรับ{TYPE_LABEL[type]}ของคุณ
                    </p>

                    {/* ระดับความยาก */}
                    <div className="mt-6">
                        <div className="text-sm font-semibold text-zinc-200 mb-3">ระดับความยาก</div>
                        <div className="grid grid-cols-3 gap-2.5">
                            {DIFFICULTIES.map((d) => {
                                const active = difficulty === d.value;
                                return (
                                    <button
                                        key={d.value}
                                        onClick={() => setDifficulty(d.value)}
                                        className={`rounded-2xl border px-2 py-3.5 text-center transition-all duration-150 ${active
                                                ? "border-indigo-500/70 bg-indigo-500/[0.09]"
                                                : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 hover:bg-zinc-900"
                                            }`}
                                    >
                                        <div className="flex justify-center mb-2">
                                            <LevelIcon level={d.level} active={active} />
                                        </div>
                                        <div className={`text-[13px] font-bold ${active ? "text-indigo-200" : "text-zinc-300"}`}>
                                            {d.label}
                                        </div>
                                        <div className={`text-[10px] mt-0.5 leading-tight ${active ? "text-indigo-300/50" : "text-zinc-600"}`}>
                                            {d.desc}
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* จำนวนตัวเลือก — เฉพาะปรนัย */}
                    {type === "mcq" && (
                        <div className="mt-6">
                            <div className="flex items-baseline justify-between mb-3">
                                <div className="text-sm font-semibold text-zinc-200">จำนวนตัวเลือก</div>
                                <div className="text-[11px] text-zinc-500">ยิ่งเยอะยิ่งเดายาก</div>
                            </div>
                            <div className="grid grid-cols-3 gap-2.5">
                                {[4, 5, 6].map((c) => {
                                    const active = choicesCount === c;
                                    return (
                                        <button
                                            key={c}
                                            onClick={() => setChoicesCount(c)}
                                            className={`rounded-2xl border px-2 py-3 text-center transition-all duration-150 ${active
                                                    ? "border-indigo-500/70 bg-indigo-500/[0.09]"
                                                    : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 hover:bg-zinc-900"
                                                }`}
                                        >
                                            <div className={`text-base font-bold ${active ? "text-indigo-200" : "text-zinc-300"}`}>
                                                {c}
                                            </div>
                                            <div className={`text-[10px] mt-0.5 ${active ? "text-indigo-300/50" : "text-zinc-600"}`}>
                                                ก – {["ง", "จ", "ฉ"][c - 4]}
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {/* จำนวนข้อ */}
                    <div className="mt-6">
                        <div className="flex items-baseline justify-between mb-3">
                            <div className="text-sm font-semibold text-zinc-200">จำนวนข้อ</div>
                            <div className="text-[11px] text-zinc-500">สร้างได้อีก {maxCount} ข้อ</div>
                        </div>

                        <div className="flex items-center gap-2.5">
                            <button
                                onClick={() => setCount(clamp(count - 1))}
                                disabled={count <= 1}
                                className="w-12 h-12 shrink-0 rounded-2xl bg-zinc-900/70 border border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-white disabled:opacity-25 transition-all flex items-center justify-center"
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                                    <line x1="5" y1="12" x2="19" y2="12" />
                                </svg>
                            </button>

                            <input
                                type="number"
                                min={1}
                                max={maxCount}
                                value={count}
                                onChange={(e) => setCount(clamp(Number(e.target.value) || 1))}
                                className="flex-1 h-12 px-3 rounded-2xl bg-zinc-900/70 border border-zinc-800 text-center text-lg font-bold text-zinc-50 outline-none focus:border-indigo-500/60 transition-all [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                            />

                            <button
                                onClick={() => setCount(clamp(count + 1))}
                                disabled={count >= maxCount}
                                className="w-12 h-12 shrink-0 rounded-2xl bg-zinc-900/70 border border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-white disabled:opacity-25 transition-all flex items-center justify-center"
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                                    <line x1="12" y1="5" x2="12" y2="19" />
                                    <line x1="5" y1="12" x2="19" y2="12" />
                                </svg>
                            </button>
                        </div>

                        {presets.length > 0 && (
                            <div className="flex gap-1.5 mt-2.5">
                                {presets.map((p) => (
                                    <button
                                        key={p}
                                        onClick={() => setCount(p)}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${count === p
                                                ? "bg-indigo-500/15 border-indigo-500/50 text-indigo-300"
                                                : "bg-zinc-900/40 border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700"
                                            }`}
                                    >
                                        {p}
                                    </button>
                                ))}
                            </div>
                        )}

                        {topicCount > 0 && !isOverTopics && (
                            <p className="mt-2.5 text-[11px] text-zinc-600">
                                เนื้อหานี้มีประมาณ {topicCount} หัวข้อ · แนะนำไม่เกิน {topicCount} ข้อ
                            </p>
                        )}

                        {isOverTopics && (
                            <div className="mt-2.5 flex gap-2 text-[11px] text-amber-400/90 bg-amber-500/[0.06] border border-amber-500/20 rounded-xl px-3 py-2 leading-relaxed">
                                <span className="shrink-0">⚠</span>
                                <span>
                                    เนื้อหามีประมาณ {topicCount} หัวข้อ — ขอ {count} ข้ออาจได้ไม่ครบ หรือมีคำถามคล้ายกัน
                                </span>
                            </div>
                        )}
                    </div>
                </div>

                <div className="flex items-center justify-between gap-3 px-7 py-4 border-t border-zinc-800/70">
                    <span className="text-[12px] text-zinc-600">รวมสูงสุด 15 ข้อต่อประเภท</span>
                    <div className="flex gap-2.5">
                        <button
                            onClick={onClose}
                            className="px-4 py-2.5 rounded-xl text-[13px] font-semibold bg-zinc-100 text-zinc-900 hover:bg-white transition-all"
                        >
                            ยกเลิก
                        </button>
                        <button
                            onClick={() => onConfirm({ count, difficulty, choicesCount })}
                            className="px-4 py-2.5 rounded-xl text-[13px] font-bold text-white bg-indigo-600 hover:bg-indigo-500 transition-all"
                        >
                            สร้างแบบทดสอบ
                        </button>
                    </div>
                </div>
            </div>
        </div>,
        document.body,
    );
}