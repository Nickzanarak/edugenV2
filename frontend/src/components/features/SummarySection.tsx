import { useState } from "react";
import { Section, DataPoint } from "../../types";

export function SummarySection({
  overview,
  keyPoints,
  sections,
  dataPoints = []
}: {
  overview: string;
  keyPoints: string[];
  sections: Section[];
  dataPoints?: DataPoint[];
}) {
  // เก็บว่าหัวข้อไหนถูกกางอยู่บ้าง (เริ่มต้นปิดทั้งหมด เพื่อให้เห็นภาพรวมก่อน)
  const [openSet, setOpenSet] = useState<Set<number>>(new Set());

  const toggleOne = (i: number) => {
    setOpenSet((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const allOpen = sections.length > 0 && openSet.size === sections.length;
  const toggleAll = () => {
    setOpenSet(allOpen ? new Set() : new Set(sections.map((_, i) => i)));
  };

  if (!overview && keyPoints.length === 0 && sections.length === 0 && dataPoints.length === 0) return null;

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700 pb-10">

      {overview && overview.trim().length > 0 && (
        <div className="relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-1000"></div>
          <div className="relative rounded-2xl bg-zinc-950 border border-zinc-800 p-8 shadow-2xl">
            <div className="flex items-center gap-3 mb-4 border-b border-zinc-800 pb-4">
              <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>
              </div>
              <h2 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-200 to-zinc-100">
                บทสรุปเนื้อหา
              </h2>
            </div>
            <p className="text-lg leading-relaxed text-zinc-300 font-light tracking-wide whitespace-pre-line">
              {overview}
            </p>
          </div>
        </div>
      )}

      {keyPoints.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            ประเด็นสำคัญ
          </h3>
          <div className="space-y-3">
            {keyPoints.map((p, i) => (
              <div key={i} className="flex gap-3 p-4 rounded-xl border border-zinc-800/60 bg-zinc-900/20 hover:border-emerald-500/30 hover:bg-emerald-900/5 transition-all group">
                <div className="shrink-0 mt-0.5">
                  <div className="w-5 h-5 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 group-hover:border-emerald-500 group-hover:bg-emerald-500 text-emerald-500 group-hover:text-black transition-all">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  </div>
                </div>
                <span className="text-base text-zinc-300 leading-relaxed group-hover:text-zinc-100 transition-colors">{p}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {sections.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
              เนื้อหาเจาะลึก
              <span className="text-xs font-normal normal-case tracking-normal text-zinc-600">
                {sections.length} หัวข้อ
              </span>
            </h3>
            <button
              type="button"
              onClick={toggleAll}
              className="text-xs px-3 py-1.5 rounded-lg border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition shrink-0"
            >
              {allOpen ? "ย่อทั้งหมด" : "ขยายทั้งหมด"}
            </button>
          </div>

          <div className="flex flex-col gap-2">
            {sections.map((s, i) => {
              const isOpen = openSet.has(i);
              return (
                <div
                  key={i}
                  className={`rounded-xl border bg-zinc-900/40 overflow-hidden transition-all ${isOpen ? "border-blue-500/30" : "border-zinc-800 hover:border-zinc-700"
                    }`}
                >
                  <button
                    type="button"
                    onClick={() => toggleOne(i)}
                    aria-expanded={isOpen}
                    className="w-full flex items-center gap-3 px-4 py-3.5 text-left hover:bg-zinc-800/40 transition-colors"
                  >
                    <span
                      className={`shrink-0 w-6 h-6 rounded-md text-xs flex items-center justify-center transition-colors ${isOpen ? "bg-blue-500/15 text-blue-300" : "bg-zinc-800 text-zinc-500"
                        }`}
                    >
                      {i + 1}
                    </span>
                    <span className={`flex-1 text-sm md:text-base font-medium leading-relaxed transition-colors ${isOpen ? "text-blue-300" : "text-zinc-200"}`}>
                      {s.title}
                    </span>
                    <svg
                      width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                      className={`shrink-0 text-zinc-500 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
                      aria-hidden="true"
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </button>

                  {isOpen && (
                    <div className="px-4 pb-4 pl-[3.25rem] animate-in fade-in slide-in-from-top-1 duration-200">
                      <p className="text-sm md:text-base text-zinc-400 leading-relaxed whitespace-pre-line">
                        {s.summary}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {dataPoints.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
            ตัวเลขสำคัญ
          </h3>
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {dataPoints.map((d, i) => {
              const value = String(d.value ?? "");
              // ปรับขนาดฟอนต์ตามความยาวค่า เพื่อให้การ์ดสูงเท่ากันเสมอ
              const size =
                value.length <= 6 ? "text-2xl" : value.length <= 12 ? "text-lg" : "text-sm";
              return (
                <div
                  key={i}
                  className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 h-[112px] flex flex-col justify-between overflow-hidden hover:border-amber-500/30 hover:bg-zinc-800/40 transition-all"
                >
                  <div className="text-xs text-zinc-500 line-clamp-2 leading-snug" title={d.label}>
                    {d.label}
                  </div>
                  <div className="flex items-baseline gap-1.5 min-w-0">
                    <span className={`font-semibold text-zinc-100 leading-tight truncate ${size}`} title={value}>
                      {value}
                    </span>
                    {d.unit && <span className="text-sm text-zinc-400 shrink-0">{d.unit}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}