import { HistoryItem } from "../../types";

export const HistorySidebar = ({
  items,
  onSelect,
  onDelete,
  onRename,
  activeId
}: {
  items: HistoryItem[],
  onSelect: (item: HistoryItem) => void,
  onDelete: (id: string) => void,
  onRename: (id: string, currentName: string) => void,
  activeId: string | null
}) => (
  <div className="flex flex-col h-full">
    <div className="p-4 border-b border-zinc-800 bg-zinc-950/50">
      <h3 className="font-semibold text-zinc-300">ประวัติการใช้งาน</h3>
    </div>
    <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
      {items.length === 0 && <p className="text-xs text-zinc-500 text-center mt-10">ยังไม่มีประวัติ</p>}
      {items.map((item) => {
        const isActive = item.id === activeId;
        return (
          <div
            key={item.id}
            onClick={() => onSelect(item)}
            className={`group rounded-xl border p-3 transition-all duration-200 cursor-pointer flex flex-col gap-2 ${
              isActive 
                ? "bg-zinc-800/60 border-indigo-500/40 shadow-[0_0_15px_rgba(99,102,241,0.05)]" 
                : "bg-zinc-900/40 border-zinc-800/60 hover:bg-zinc-800/40 hover:border-zinc-700/80"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="font-medium text-sm text-zinc-200 truncate flex-1 leading-relaxed" title={item.fileName}>
                {item.fileName}
              </div>
              
              <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 -mt-1 -mr-1">
                <button
                  onClick={(e) => { e.stopPropagation(); onRename(item.id, item.fileName); }}
                  className="p-1.5 text-zinc-500 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-md transition-colors"
                  title="เปลี่ยนชื่อ"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
                  className="p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors"
                  title="ลบ"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
                </button>
              </div>
            </div>

            <div className="flex justify-between items-end text-xs">
              <span className="text-zinc-500 font-light">{new Date(item.timestamp).toLocaleDateString('th-TH')}</span>
              {item.totalQuestions > 0 ? (
                item.score >= 0 ? (
                  <span className={`px-2 py-0.5 rounded font-medium border ${item.score >= item.totalQuestions / 2 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>
                    {item.score}/{item.totalQuestions}
                  </span>
                ) : (
                  <span className="text-zinc-500 bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700/50">รอสอบ</span>
                )
              ) : (
                <span className="text-zinc-500 bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700/50">รอสอบ</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  </div>
);
