"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";

type Props = {
    open: boolean;
    onClose: () => void;
    onLogin: () => void;
};

/** popup แจ้งว่าต้องเข้าสู่ระบบก่อน พร้อมปุ่มพาไปหน้าเข้าสู่ระบบทันที
 *  ใช้แทนการแสดงข้อความ error ดิบ ๆ จาก API (เช่น "Missing or invalid authentication")
 */
export function LoginRequiredModal({ open, onClose, onLogin }: Props) {
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    if (!open || typeof document === "undefined") return null;

    return createPortal(
        <div
            className="fixed inset-0 z-[95] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
            onClick={onClose}
            role="dialog"
            aria-modal="true"
            aria-label="ต้องเข้าสู่ระบบก่อน"
        >
            <div
                className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="p-6 flex flex-col items-center text-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 flex items-center justify-center">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                    </div>
                    <div className="font-bold text-lg text-zinc-100">ต้องเข้าสู่ระบบก่อน</div>
                    <p className="text-sm text-zinc-400 leading-relaxed">
                        ฟีเจอร์นี้ใช้ทรัพยากร AI จึงต้องเข้าสู่ระบบก่อนใช้งาน
                        <br />
                        เข้าสู่ระบบแล้วผลงานของคุณจะถูกบันทึกไว้ให้ด้วย
                    </p>
                </div>
                <div className="px-6 py-4 border-t border-zinc-800 flex justify-end gap-2">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-xl text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition"
                    >
                        ไว้ก่อน
                    </button>
                    <button
                        onClick={onLogin}
                        className="px-5 py-2 rounded-xl text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-500 transition"
                    >
                        เข้าสู่ระบบ
                    </button>
                </div>
            </div>
        </div>,
        document.body,
    );
}