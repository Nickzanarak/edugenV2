"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

type Props = {
    open: boolean;
    setTitle: string;
    onCancel: () => void;
    onConfirm: (showAnswers: boolean) => void;
};

/** popup เลือกรูปแบบไฟล์ก่อนส่งออกชุดข้อสอบ
 *  ค่าเริ่มต้นคือ "ข้อสอบอย่างเดียว" เพื่อไม่ให้เผลอแจกไฟล์ที่มีเฉลยไปให้ผู้สอบ
 */
export function ExportOptionsModal({ open, setTitle, onCancel, onConfirm }: Props) {
    const [withAnswers, setWithAnswers] = useState(false);

    // รีเซ็ตทุกครั้งที่เปิดใหม่ จะได้ไม่ค้างค่าจากครั้งก่อน
    useEffect(() => {
        if (open) setWithAnswers(false);
    }, [open]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onCancel();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onCancel]);

    if (!open || typeof document === "undefined") return null;

    const options = [
        {
            value: false,
            title: "ข้อสอบอย่างเดียว",
            desc: "สำหรับพิมพ์แจกให้ผู้สอบทำ",
        },
        {
            value: true,
            title: "ข้อสอบ พร้อมเฉลย",
            desc: "เฉลยอยู่หน้าสุดท้าย แยกจากตัวข้อสอบ",
        },
    ];

    return createPortal(
        <div
            className="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
            onClick={onCancel}
            role="dialog"
            aria-modal="true"
            aria-label="เลือกรูปแบบการส่งออก"
        >
            <div
                className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="px-5 py-4 border-b border-zinc-800">
                    <div className="font-bold text-lg text-zinc-100">ส่งออกชุดข้อสอบ</div>
                    <div className="text-xs text-zinc-500 mt-0.5 truncate">ชุด: {setTitle}</div>
                </div>

                <div className="p-5 space-y-2.5">
                    {options.map((opt) => {
                        const selected = withAnswers === opt.value;
                        return (
                            <button
                                key={String(opt.value)}
                                type="button"
                                onClick={() => setWithAnswers(opt.value)}
                                className={`w-full text-left rounded-xl border p-4 transition-all ${selected
                                        ? "border-indigo-500/50 bg-indigo-500/10"
                                        : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-700"
                                    }`}
                            >
                                <div className="flex items-start gap-3">
                                    <span
                                        className={`mt-0.5 w-4 h-4 rounded-full border-2 shrink-0 flex items-center justify-center ${selected ? "border-indigo-400" : "border-zinc-600"
                                            }`}
                                    >
                                        {selected && <span className="w-2 h-2 rounded-full bg-indigo-400" />}
                                    </span>
                                    <span className="min-w-0">
                                        <span className={`block text-sm font-semibold ${selected ? "text-indigo-200" : "text-zinc-200"}`}>
                                            {opt.title}
                                        </span>
                                        <span className="block text-xs text-zinc-500 mt-0.5">{opt.desc}</span>
                                    </span>
                                </div>
                            </button>
                        );
                    })}
                </div>

                <div className="px-5 py-4 border-t border-zinc-800 flex justify-end gap-2">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 rounded-xl text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition"
                    >
                        ยกเลิก
                    </button>
                    <button
                        onClick={() => onConfirm(withAnswers)}
                        className="px-5 py-2 rounded-xl text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-500 transition"
                    >
                        ส่งออก
                    </button>
                </div>
            </div>
        </div>,
        document.body,
    );
}