import { ReactNode } from "react";

export const Label = ({ children }: { children: ReactNode }) => (
  <span className="inline-flex items-center gap-2 text-xs rounded-full px-2 py-1 bg-zinc-800/60 border border-zinc-700/60">
    {children}
  </span>
);
