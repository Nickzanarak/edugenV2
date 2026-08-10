"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";

type Props = {
    open: boolean;
    title: string;
    message?: string;
    confirmText?: string;
    danger?: boolean;
    onCancel: () => void;
    onConfirm: () => void;
};

/** popup ยืนยันในธีมเดียวกับเว็บ ใช้แทน confirm() ของเบราว์เซอร์ */
export function ConfirmModal({
    open,
    title,
    message,
    confirmText = "ยืนยัน",
    danger = false,
    onCancel,
    onConfirm,
}: Props) {
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onCancel();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onCancel]);

    if (!open || typeof document === "undefined") return null;

    return createPortal(
        <div
            className="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200"
            onClick={onCancel}
            role="dialog"
            aria-modal="true"
            aria-label={title}
        >
            <div
                className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="p-6 space-y-2">
                    <div className="font-bold text-lg text-zinc-100">{title}</div>
                    {message && <p className="text-sm text-zinc-400 leading-relaxed">{message}</p>}
                </div>
                <div className="px-6 py-4 border-t border-zinc-800 flex justify-end gap-2">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 rounded-xl text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition"
                    >
                        ยกเลิก
                    </button>
                    <button
                        onClick={onConfirm}
                        className={`px-5 py-2 rounded-xl text-sm font-semibold text-white transition ${danger ? "bg-red-600 hover:bg-red-500" : "bg-indigo-600 hover:bg-indigo-500"
                            }`}
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>,
        document.body,
    );
}