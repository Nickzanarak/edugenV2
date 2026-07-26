import { Section } from "../../types";

export function SummarySection({
  overview,
  keyPoints,
  sections
}: {
  overview: string;
  keyPoints: string[];
  sections: Section[];
}) {
  if (!overview && keyPoints.length === 0 && sections.length === 0) return null;

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
          <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            เนื้อหาเจาะลึก
          </h3>
          <div className="flex flex-col gap-4">
            {sections.map((s, i) => (
              <div key={i} className="group relative rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 md:p-6 hover:border-blue-500/30 hover:bg-zinc-800 transition-all">
                <div className="absolute top-0 left-0 w-1 h-full bg-blue-600 rounded-l-xl opacity-0 group-hover:opacity-100 transition-all"></div>
                <h4 className="text-base md:text-lg font-bold text-zinc-200 mb-2 group-hover:text-blue-400 transition-colors flex items-center gap-2">
                  {s.title}
                </h4>
                <p className="text-sm md:text-base text-zinc-400 leading-relaxed group-hover:text-zinc-300">
                  {s.summary}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
