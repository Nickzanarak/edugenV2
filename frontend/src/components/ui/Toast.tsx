"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

type ToastKind = "success" | "error" | "info";

type ToastItem = {
    id: number;
    message: string;
    kind: ToastKind;
};

type ToastContextValue = {
    /** แสดงข้อความแจ้งเตือนมุมขวาบน แล้วหายเองใน 3 วินาที */
    showToast: (message: string, kind?: ToastKind) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

/** ใช้เรียกแจ้งเตือนจากคอมโพเนนต์ไหนก็ได้ที่อยู่ใต้ ToastProvider */
export function useToast(): ToastContextValue {
    const ctx = useContext(ToastContext);
    // ถ้าลืมครอบ Provider ให้ทำงานต่อได้ ไม่ให้แอปล่ม
    return ctx ?? { showToast: () => { } };
}

const STYLES: Record<ToastKind, string> = {
    success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    error: "border-red-500/30 bg-red-500/10 text-red-300",
    info: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300",
};

function ToastIcon({ kind }: { kind: ToastKind }) {
    if (kind === "success") {
        return (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="20 6 9 17 4 12" />
            </svg>
        );
    }
    if (kind === "error") {
        return (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
        );
    }
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
            <circle cx="12" cy="12" r="10" strokeWidth="2" />
        </svg>
    );
}

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);
    const [mounted, setMounted] = useState(false);

    useEffect(() => setMounted(true), []);

    const showToast = useCallback((message: string, kind: ToastKind = "success") => {
        const id = Date.now() + Math.random();
        setToasts((prev) => [...prev, { id, message, kind }]);
        setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id));
        }, 3000);
    }, []);

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            {mounted &&
                createPortal(
                    <div
                        className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none"
                        role="status"
                        aria-live="polite"
                    >
                        {toasts.map((t) => (
                            <div
                                key={t.id}
                                className={`flex items-center gap-2.5 px-4 py-3 rounded-xl border backdrop-blur-md shadow-lg text-sm font-medium animate-in slide-in-from-right-4 fade-in duration-300 ${STYLES[t.kind]}`}
                            >
                                <ToastIcon kind={t.kind} />
                                <span>{t.message}</span>
                            </div>
                        ))}
                    </div>,
                    document.body,
                )}
        </ToastContext.Provider>
    );
}