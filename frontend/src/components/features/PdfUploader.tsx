export function PdfUploader({ 
  onUpload 
}: { 
  onUpload: (file: File | null) => void 
}) {
  return (
    <div className="relative">
      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => onUpload(e.target.files?.[0] || null)}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
      />
      <button className="p-2 rounded-full hover:bg-zinc-800 text-zinc-400 transition flex items-center justify-center gap-1" title="อัปโหลด PDF">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
        <span className="text-xs font-medium">PDF</span>
      </button>
    </div>
  );
}
