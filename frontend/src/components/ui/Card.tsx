import { ReactNode } from "react";

export const Card = ({ className = "", children }: { className?: string; children: ReactNode }) => (
  <div className={`rounded-2xl border border-zinc-800/40 bg-zinc-900/40 backdrop-blur-sm p-5 ${className}`}>
    {children}
  </div>
);
