"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type Props = {
    open: boolean;
    title: string;
    label?: string;
    defaultValue?: string;
    confirmText?: string;
    onCancel: () => void;
    onConfirm: (value: string) => void;
};

/** popup กรอกข้อความในธีมเดียวกับเว็บ ใช้แทน prompt() ของเบราว์เซอร์ */
export function PromptModal({
    open,
    title,
    label,
    defaultValue = "",
    confirmText = "บันทึก",
    onCancel,
    onConfirm,
}: Props) {
    const [value, setValue] = useState(defaultValue);
    const inputRef = useRef<HTMLInputElement>(null);

    // ทุกครั้งที่เปิด ให้ตั้งค่าเริ่มต้นใหม่ + โฟกัสและเลือกข้อความไว้ให้เลย
    useEffect(() => {
        if (open) {
            setValue(defaultValue);
            setTimeout(() => inputRef.current?.select(), 50);
        }
    }, [open, defaultValue]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onCancel();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onCancel]);

    if (!open || typeof document === "undefined") return null;

    const submit = () => {
        const v = value.trim();
        if (!v) return;
        onConfirm(v);
    };

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
                <div className="px-5 py-4 border-b border-zinc-800">
                    <div className="font-bold text-lg text-zinc-100">{title}</div>
                </div>
                <div className="p-5 space-y-3">
                    {label && <label className="block text-sm text-zinc-400">{label}</label>}
                    <input
                        ref={inputRef}
                        className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-4 py-3 text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter") submit();
                        }}
                        placeholder="พิมพ์ชื่อ…"
                    />
                </div>
                <div className="px-5 py-4 border-t border-zinc-800 flex justify-end gap-2">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 rounded-xl text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition"
                    >
                        ยกเลิก
                    </button>
                    <button
                        onClick={submit}
                        disabled={!value.trim()}
                        className="px-5 py-2 rounded-xl text-sm font-semibold bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-600 transition"
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>,
        document.body,
    );
}