// รับ prop ชื่อ onUpload เป็นฟังก์ชันที่จะถูกเรียกเมื่อผู้ใช้เลือกไฟล์ (ส่งไฟล์ หรือ null ถ้าไม่ได้เลือก)
export function PdfUploader({
  onUpload
}: {
  onUpload: (file: File | null) => void
}) {
  return (
    // relative: ให้ input ข้างในวางซ้อนทับปุ่มได้พอดี
    <div className="relative">
      <input
        type="file"
        accept="application/pdf" // จำกัดให้เลือกได้เฉพาะไฟล์ PDF
        aria-label="เลือกไฟล์ PDF" // ข้อความสำหรับ screen reader
        onChange={(e) => onUpload(e.target.files?.[0] || null)} // เอาไฟล์แรกที่เลือกส่งให้ onUpload ถ้าไม่มีส่ง null
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
      />
      {/* หน้าตาปุ่ม*/}
      <button aria-label="อัปโหลดไฟล์ PDF" className="p-2 rounded-full hover:bg-zinc-800 text-zinc-400 transition flex items-center justify-center gap-1" title="อัปโหลด PDF">
        {/* ไอคอนรูปคลิปหนีบกระดาษ */}
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
        {/* ข้อความ "PDF" ข้างไอคอน */}
        <span className="text-xs font-medium">PDF</span>
      </button>
    </div>
  );
}