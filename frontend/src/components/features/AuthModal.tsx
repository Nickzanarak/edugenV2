import { useState } from "react";
import { signInWithEmailAndPassword, createUserWithEmailAndPassword } from "firebase/auth";
import { auth } from "../../lib/firebase";

export function AuthModal({ 
  open, 
  onClose 
}: { 
  open: boolean; 
  onClose: () => void; 
}) {
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  if (!open) return null;

  const handleAuthSubmit = async () => {
    if (!authEmail.trim() || !authPassword.trim()) { 
      setAuthError("กรุณากรอกอีเมลและรหัสผ่าน"); 
      return; 
    }
    setAuthError(null); 
    setAuthLoading(true);
    try {
      if (authMode === "login") {
        await signInWithEmailAndPassword(auth, authEmail.trim(), authPassword);
      } else {
        await createUserWithEmailAndPassword(auth, authEmail.trim(), authPassword);
      }
      onClose(); 
      setAuthEmail(""); 
      setAuthPassword("");
    } catch (err: unknown) {
      console.error(err);
      setAuthError("เกิดข้อผิดพลาด กรุณาลองอีกครั้ง");
    } finally { 
      setAuthLoading(false); 
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div 
        className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-in fade-in duration-300" 
        onClick={onClose} 
      />
      
      <div className="relative w-full max-w-md rounded-3xl border border-zinc-800/80 bg-zinc-950/80 p-8 shadow-2xl shadow-indigo-900/10 backdrop-blur-xl animate-in zoom-in-95 fade-in duration-300">
        
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-zinc-500 hover:text-white hover:bg-zinc-800 rounded-full transition"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>

        <div className="text-center mb-8">
          <h2 className="text-3xl font-extrabold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent mb-2">
            {authMode === "login" ? "ยินดีต้อนรับ" : "สร้างบัญชีใหม่"}
          </h2>
          <p className="text-zinc-400 text-sm">
            {authMode === "login" ? "เข้าสู่ระบบเพื่อใช้งาน EduGen " : "เริ่มต้นใช้งาน EduGen เพื่อสรุปและสร้างข้อสอบ"}
          </p>
        </div>

        {authError && (
          <div className="mb-6 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200 flex items-center gap-3">
            {authError}
          </div>
        )}

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-zinc-400 pl-1">อีเมล</label>
            <input 
              type="email" 
              className="w-full rounded-2xl bg-zinc-900/50 border border-zinc-800 px-4 py-3.5 text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all" 
              value={authEmail} 
              onChange={(e) => setAuthEmail(e.target.value)} 
              placeholder="you@example.com" 
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-zinc-400 pl-1">รหัสผ่าน</label>
            <input 
              type="password" 
              className="w-full rounded-2xl bg-zinc-900/50 border border-zinc-800 px-4 py-3.5 text-zinc-100 placeholder-zinc-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all" 
              value={authPassword} 
              onChange={(e) => setAuthPassword(e.target.value)} 
              placeholder="อย่างน้อย 6 ตัวอักษร" 
              onKeyDown={(e) => { if(e.key === 'Enter') handleAuthSubmit(); }}
            />
          </div>

          <button 
            onClick={handleAuthSubmit} 
            disabled={authLoading}
            className="w-full mt-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-3.5 font-semibold text-white shadow-lg shadow-indigo-500/25 hover:from-indigo-500 hover:to-purple-500 hover:shadow-indigo-500/40 transition-all disabled:opacity-50 flex justify-center items-center gap-2"
          >
            {authLoading ? (
              <span className="animate-pulse">กำลังดำเนินการ...</span>
            ) : (
              authMode === "login" ? "เข้าสู่ระบบ" : "สมัครสมาชิก"
            )}
          </button>
        </div>

        <div className="mt-8 text-center text-sm text-zinc-500">
          {authMode === "login" ? "ยังไม่มีบัญชีใช่ไหม? " : "มีบัญชีอยู่แล้วใช่ไหม? "}
          <button 
            onClick={() => { setAuthError(null); setAuthMode((m) => (m === "login" ? "register" : "login")); }} 
            className="font-medium text-indigo-400 hover:text-indigo-300 hover:underline transition"
          >
            {authMode === "login" ? "สมัครสมาชิกที่นี่" : "เข้าสู่ระบบเลย"}
          </button>
        </div>

      </div>
    </div>
  );
}
