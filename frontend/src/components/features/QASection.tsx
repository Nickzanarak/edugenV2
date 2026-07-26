import type { QAPair } from "../../types";

type Props = {
  qaInput: string;
  qaHistory: QAPair[];
  loading: boolean;
  onInputChange: (value: string) => void;
  onAsk: () => void;
};

export function QASection({ qaInput, qaHistory, loading, onInputChange, onAsk }: Props) {
  return (
    <div>
      <div className="group relative flex items-center bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-2 pr-2 shadow-xl backdrop-blur-md transition-all duration-300 focus-within:border-indigo-500/50 focus-within:bg-zinc-900/80 focus-within:shadow-indigo-500/10 hover:border-zinc-700/80">
        <div className="pl-4 pr-2 text-zinc-500 group-focus-within:text-indigo-400 transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        </div>
        <input
          className="flex-1 bg-transparent border-0 py-3 px-2 text-zinc-100 placeholder-zinc-600 focus:outline-none text-base w-full"
          placeholder="สงสัยตรงไหน? พิมพ์ถาม AI จากเนื้อหาได้เลย..."
          value={qaInput}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") onAsk(); }}
        />
        <button
          onClick={onAsk}
          disabled={loading || !qaInput.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white px-6 py-3 rounded-xl font-semibold transition-all flex items-center gap-2"
        >
          ส่ง
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="-mr-1"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
        </button>
      </div>

      {qaHistory.length > 0 && (
        <div className="space-y-4 mt-6 animate-in fade-in duration-500">
          {qaHistory.map((item, idx) => (
            <div key={idx} className="relative rounded-2xl border border-zinc-800/60 bg-zinc-950/50 overflow-hidden shadow-lg">
              <div className="px-5 py-4 bg-zinc-900/40 border-b border-zinc-800/50 flex items-start gap-4">
                <div className="mt-0.5 shrink-0 w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center border border-zinc-700 shadow-sm text-zinc-400">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                </div>
                <div className="text-zinc-200 font-medium leading-relaxed mt-0.5">{item.question}</div>
              </div>
              <div className="px-5 py-5 flex items-start gap-4">
                <div className="mt-0.5 shrink-0 w-8 h-8 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 flex items-center justify-center shadow-sm">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a2 2 0 0 1 2 2c-.11.66-.4 1.25-.83 1.76A5.5 5.5 0 0 1 17.5 11h1a1.5 1.5 0 0 1 0 3h-1a5.5 5.5 0 0 1-4.33 5.24c.43.51.72 1.1.83 1.76a2 2 0 0 1-4 0c.11-.66.4-1.25.83-1.76A5.5 5.5 0 0 1 5.5 14h-1a1.5 1.5 0 0 1 0-3h1a5.5 5.5 0 0 1 4.33-5.24C9.4 5.25 9.11 4.66 9 4a2 2 0 0 1 3-2z"></path></svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-zinc-300 leading-relaxed whitespace-pre-line font-light mt-0.5">{item.answer}</div>
                  {item.source && (
                    <div className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900/70 border border-zinc-800 text-[11px] text-zinc-500">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      อ้างอิงจาก {item.source}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}