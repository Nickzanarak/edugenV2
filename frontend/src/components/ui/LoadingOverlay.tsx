export function LoadingOverlay({ loadingText }: { loadingText: string }) {
  if (!loadingText) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300"></div>
      <div className="relative bg-zinc-900/90 border border-zinc-700/50 shadow-[0_0_50px_rgba(99,102,241,0.15)] rounded-3xl p-8 flex flex-col items-center gap-6 animate-in zoom-in-95 fade-in duration-300 min-w-[320px] max-w-sm text-center">
        <div className="relative flex items-center justify-center w-20 h-20">
          {/* Outer spinning ring */}
          <div className="absolute inset-0 rounded-full border-[3px] border-zinc-800"></div>
          <div className="absolute inset-0 rounded-full border-[3px] border-indigo-500 border-t-transparent animate-spin"></div>
          {/* Inner glowing element */}
          <div className="w-8 h-8 bg-indigo-500/20 rounded-full blur-md animate-pulse"></div>
          <svg className="absolute text-indigo-400 w-8 h-8 animate-pulse" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v4"></path>
            <path d="M12 18v4"></path>
            <path d="M4.93 4.93l2.83 2.83"></path>
            <path d="M16.24 16.24l2.83 2.83"></path>
            <path d="M2 12h4"></path>
            <path d="M18 12h4"></path>
            <path d="M4.93 19.07l2.83-2.83"></path>
            <path d="M16.24 7.76l2.83-2.83"></path>
          </svg>
        </div>
        <div className="space-y-2">
          <h3 className="text-zinc-100 font-bold text-lg tracking-wide">{loadingText}</h3>
          <p className="text-zinc-500 text-sm">กรุณารอสักครู่ ระบบกำลังประมวลผล...</p>
        </div>
      </div>
    </div>
  );
}
