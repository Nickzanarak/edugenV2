"use client";
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { auth } from "../src/lib/firebase";
import { onIdTokenChanged, signOut, type User } from "firebase/auth";
import { Section, DataPoint, QAPair, HistoryItem, QuizItem } from "../src/types";
import { parseApi } from "../src/lib/validate";
import { PdfExtractSchema, SummarizeResponseSchema } from "../src/schemas/api";
import { apiFetch, ApiError, buildAuthHeaders, canUseProtectedApi, isDemoAuthEnabled } from "../src/services/api";
import {
  buildHistoryPayload,
} from "../src/services/history";
import { useHistoryMutations, useHistoryQuery } from "../src/hooks/useHistoryQuery";
import { Card } from "../src/components/ui/Card";
import { Label } from "../src/components/ui/Label";
import { PrimaryBtn } from "../src/components/ui/PrimaryBtn";
import { Modal } from "../src/components/ui/Modal";
import { HistorySidebar } from "../src/components/layout/HistorySidebar";
import { useToast } from "../src/components/ui/Toast";
import { PromptModal } from "../src/components/ui/PromptModal";
import { ConfirmModal } from "../src/components/ui/ConfirmModal";
import { LoginRequiredModal } from "../src/components/ui/LoginRequiredModal";
import { useTypewriter } from "../src/hooks/useTypewriter";
import { useQuiz } from "../src/hooks/useQuiz";
import { useBank } from "../src/hooks/useBank";
import { useQA } from "../src/hooks/useQA";
import { AuthModal } from "../src/components/features/AuthModal";
import { SummarySection } from "../src/components/features/SummarySection";
import { PdfUploader } from "../src/components/features/PdfUploader";
import { QASection } from "../src/components/features/QASection";
import { QuizSection } from "../src/components/features/QuizSection";
import { QuizToolbar } from "../src/components/features/QuizToolbar";
import { BankPanel } from "../src/components/features/BankPanel";
/* ---------- Page ---------- */
export default function Home() {
  // -------- Auth / Notes --------
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [demoUid, setDemoUid] = useState("demo-user");
  const authHeader = useMemo(() => buildAuthHeaders(authToken, demoUid), [authToken, demoUid]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);

  // --- UI States ---
  const [isLanding, setIsLanding] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // State สำหรับ Animation เมาส์
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  const welcomeText = useTypewriter("สวัสดีครับ, มีอะไรให้ช่วยไหม?", 60, 3000);

  const [currentHistoryId, setCurrentHistoryId] = useState<string | null>(null);
  const [hiddenContext, setHiddenContext] = useState<string>("");

  const { data: historyItems = [] } = useHistoryQuery(authHeader, !!currentUser, authReady);

  const {
    patchLocal: patchHistoryLocal,
    invalidate: invalidateHistory,
    deleteMutation: deleteHistoryMutation,
    renameMutation: renameHistoryMutation,
    saveHistory,
  } = useHistoryMutations(authHeader);

  const setHistoryItems = useCallback((
    action: HistoryItem[] | ((prev: HistoryItem[]) => HistoryItem[]),
  ) => {
    patchHistoryLocal((items) => (typeof action === "function" ? action(items) : action));
  }, [patchHistoryLocal]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isLanding) {
      setMousePosition({ x: e.clientX, y: e.clientY });
    }
  }, [isLanding]);

  useEffect(() => {
    // ใช้ onIdTokenChanged แทน onAuthStateChanged
    // token ของ Firebase หมดอายุทุก 1 ชั่วโมงและถูกต่ออายุอัตโนมัติ
    // ถ้าใช้ onAuthStateChanged จะรับรู้เฉพาะตอนเข้า/ออกจากระบบ ทำให้ระบบถือ token เก่าที่หมดอายุแล้ว
    const unsub = onIdTokenChanged(auth, async (user) => {
      if (user) {
        try {
          const token = await user.getIdToken();
          setCurrentUser(user);
          setAuthToken(token);
        } catch (e) {
          console.error("Auth Error:", e);
        }
      } else {
        setCurrentUser(null);
        setAuthToken(null);
        if (!isDemoAuthEnabled()) invalidateHistory();
        try {
          const uid = localStorage.getItem("uid");
          setDemoUid(uid?.trim() || "demo-user");
        } catch {
          setDemoUid("demo-user");
        }
      }

      setAuthReady(true);
    });

    // ขอ token ใหม่ทุก 50 นาที (อายุจริง 60 นาที) เผื่อผู้ใช้เปิดหน้าเว็บทิ้งไว้นาน
    // onIdTokenChanged ด้านบนจะรับค่าใหม่เอง
    const refreshTimer = window.setInterval(() => {
      auth.currentUser?.getIdToken(true).catch(() => { /* รอบหน้าลองใหม่ */ });
    }, 50 * 60 * 1000);

    return () => {
      unsub();
      window.clearInterval(refreshTimer);
    };
  }, [invalidateHistory]);

  const [loadingText, setLoadingText] = useState<string>("");
  const { showToast } = useToast();
  // popup เปลี่ยนชื่อ / ยืนยันลบประวัติ (ใช้แทน prompt/confirm ของเบราว์เซอร์)
  const [renameHistoryTarget, setRenameHistoryTarget] = useState<{ id: string; name: string } | null>(null);
  const [deleteHistoryTarget, setDeleteHistoryTarget] = useState<string | null>(null);
  const [loginRequired, setLoginRequired] = useState(false);

  const deleteHistory = async (id: string) => {
    setDeleteHistoryTarget(id);
  };

  const renameHistory = async (id: string, currentName: string) => {
    setRenameHistoryTarget({ id, name: currentName });
  };


  const handleLogout = async () => { try { await signOut(auth); } catch (err) { console.error(err); } };

  const [fileId, setFileId] = useState<string>("manual");
  const [note, setNote] = useState<string>("");
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteStatus, setNoteStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [noteUpdatedAt, setNoteUpdatedAt] = useState<string | null>(null);
  const saveTimer = useRef<number | null>(null);
  const firstLoadRef = useRef<boolean>(true);

  const loadNote = useCallback(async (fid: string) => {
    if (!fid || !canUseProtectedApi(!!currentUser)) return;
    try {
      const json = await apiFetch<{ content?: string; updated_at?: string }>(
        `/notes/${encodeURIComponent(fid)}`,
        { auth: authHeader },
      );
      setNote(typeof json?.content === "string" ? json.content : "");
      setNoteUpdatedAt(typeof json?.updated_at === "string" ? json.updated_at : null);
      setNoteStatus("idle");
      firstLoadRef.current = false;
    } catch { setNote(""); setNoteUpdatedAt(null); setNoteStatus("error"); }
  }, [currentUser, authHeader]);
  const autosaveNote = useCallback(async (fid: string, content: string) => {
    if (!fid || !canUseProtectedApi(!!currentUser)) return;
    try {
      setNoteStatus("saving");
      const json = await apiFetch<{ updated_at?: string }>(
        `/notes/${encodeURIComponent(fid)}`,
        { method: "PUT", auth: authHeader, json: { content } },
      );
      setNoteUpdatedAt(typeof json?.updated_at === "string" ? json.updated_at : null);
      setNoteStatus("saved");
    } catch { setNoteStatus("error"); }
  }, [currentUser, authHeader]);
  useEffect(() => {
    if (firstLoadRef.current) return;
    if (!fileId) return;
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => { autosaveNote(fileId, note); }, 1200);
    return () => { if (saveTimer.current) window.clearTimeout(saveTimer.current); };
  }, [note, fileId, autosaveNote]);

  /* -------- App states -------- */
  const [text, setText] = useState("");
  const [pdf, setPdf] = useState<File | null>(null);
  const [pdfText, setPdfText] = useState("");
  const [overview, setOverview] = useState("");
  const [keyPoints, setKeyPoints] = useState<string[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [dataPoints, setDataPoints] = useState<DataPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  /** แปลง error จาก API เป็นข้อความที่ผู้ใช้เข้าใจ
   *  ถ้าเป็น 401 (ยังไม่ได้เข้าสู่ระบบ) จะเปิด popup ชวนเข้าสู่ระบบแทน */
  const handleApiError = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) {
      setLoginRequired(true);
      return;
    }
    setError(e instanceof Error ? e.message : String(e));
  }, []);

  /** ใช้กับ hook ที่ส่งข้อความ error มาเป็น string
   *  ถ้าเป็นข้อความจากการยืนยันตัวตน ให้เปิด popup ชวนเข้าสู่ระบบแทน */
  const handleErrorText = useCallback((msg: string | null) => {
    if (msg && /authentication|auth token|unauthorized|401/i.test(msg)) {
      setLoginRequired(true);
      setError(null);
      return;
    }
    setError(msg);
  }, []);

  const context = useMemo(() => {
    const manualInput = [text.trim(), pdfText.trim()].filter(Boolean).join("\n");
    return manualInput || hiddenContext;
  }, [text, pdfText, hiddenContext]);

  const quiz = useQuiz(context, authHeader);
  const bank = useBank(authHeader);
  const qa = useQA(authHeader);

  const { resetQuiz, restoreFromHistory, questions, answers, score, lockedCount, countByType, handleAnswerChange, isOverallSubmitted, isAllAnswered, ensureTopics, addMoreQuiz, submitQuiz } = quiz;
  const { resetQA, setQaHistory, qaHistory, qaInput, setQaInput, askQA } = qa;

  const handleNewSession = useCallback(() => {
    setIsLanding(true);
    setCurrentHistoryId(null);
    setText("");
    setPdf(null);
    setPdfText("");
    setOverview("");
    setKeyPoints([]);
    setSections([]);
    setDataPoints([]);
    resetQuiz();
    resetQA();
    setHiddenContext("");
    setFileId("manual");
  }, [resetQuiz, resetQA]);

  const loadFromHistory = useCallback((item: HistoryItem) => {
    setIsLanding(false);
    setCurrentHistoryId(item.id);
    setFileId(item.id);
    setOverview(item.overview || "");
    setKeyPoints(item.keyPoints || []);
    setSections(item.sections || []);
    setDataPoints(item.dataPoints || []);
    restoreFromHistory(item);
    setHiddenContext(item.content || "");
    setText("");
    setPdf(null);
    setPdfText("");
    setQaHistory(item.qa_history || []);
  }, [restoreFromHistory, setQaHistory]);

  const uploadPdf = async (file: File | null) => {
    setPdf(file); setPdfText("");
    setHiddenContext("");

    const fid = currentHistoryId ? currentHistoryId : (file ? file.name.replace(/\.pdf$/i, "") || "pdf-file" : "manual");
    setFileId(fid);

    firstLoadRef.current = true;
    await loadNote(fid);

    if (file) {
      setIsLanding(false);
      setLoading(true);
      const sizeMB = file.size / (1024 * 1024);
      setLoadingText(
        sizeMB > 2
          ? "กำลังอ่านไฟล์ PDF และวิเคราะห์รูปภาพ… ไฟล์ขนาดใหญ่อาจใช้เวลา 1-2 นาที"
          : "กำลังอ่านข้อมูลจากไฟล์ PDF..."
      );
    }

    if (!file) return;

    try {
      const fd = new FormData(); fd.append("pdf", file);
      const raw = await apiFetch<unknown>("/pdf/extract", { method: "POST", auth: authHeader, body: fd });
      const json = parseApi(PdfExtractSchema, raw, "pdf extract");
      setPdfText(json.text);
      resetQuiz();
      await ensureTopics();
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
      setLoadingText(""); // 🟢 ปิด Loading Overlay
    }
  };

  // 🟢 Helper: Update History Item Locally
  const updateLocalHistoryItem = useCallback((newItemData: Partial<HistoryItem>) => {
    if (!currentHistoryId) return;
    setHistoryItems((prev) =>
      prev.map((item) =>
        item.id === currentHistoryId ? { ...item, ...newItemData } : item
      )
    );
  }, [currentHistoryId, setHistoryItems]);

  const persistSessionHistory = useCallback(async (
    overrides: Partial<{
      overview: string;
      keyPoints: string[];
      sections: Section[];
      dataPoints: DataPoint[];
      questions: QuizItem[];
      answers: Record<number, string>;
      score: number;
      qaHistory: QAPair[];
      manualFallback: string;
    }>,
  ) => {
    if (!canUseProtectedApi(!!currentUser)) return null;
    const payload = buildHistoryPayload({
      pdf,
      currentHistoryId,
      historyItems,
      fileId,
      overview: overrides.overview ?? overview,
      keyPoints: overrides.keyPoints ?? keyPoints,
      sections: overrides.sections ?? sections,
      dataPoints: overrides.dataPoints ?? dataPoints,
      questions: overrides.questions ?? questions,
      answers: overrides.answers ?? answers,
      score: overrides.score ?? (score !== null ? score : -1),
      content: context,
      qaHistory: overrides.qaHistory ?? qaHistory,
      manualFallback: overrides.manualFallback,
    });
    const saved = await saveHistory.mutateAsync({ currentHistoryId, payload });
    if (saved?.id) {
      setCurrentHistoryId(saved.id);
      await autosaveNote(saved.id, note);
      setFileId(saved.id);
      return saved.id;
    }
    return currentHistoryId;
  }, [
    currentUser, pdf, currentHistoryId, historyItems, fileId,
    overview, keyPoints, sections, dataPoints, questions, answers, score, qaHistory,
    context, autosaveNote, note, saveHistory,
  ]);

  const persistQuizUpdate = useCallback(async (newQuestions: QuizItem[]) => {
    if (!canUseProtectedApi(!!currentUser)) return;
    if (currentHistoryId) {
      const payload = buildHistoryPayload({
        pdf, currentHistoryId, historyItems, fileId,
        overview, keyPoints, sections, dataPoints,
        questions: newQuestions, answers: answers, score: -1,
        content: context, qaHistory: qaHistory,
      });
      await saveHistory.mutateAsync({ currentHistoryId, payload });
      updateLocalHistoryItem({
        totalQuestions: newQuestions.length,
        lockedCount: lockedCount,
        answers: answers,
        questions: newQuestions,
      });
    } else {
      await persistSessionHistory({ questions: newQuestions, score: -1 });
    }
  }, [currentUser, pdf, currentHistoryId, historyItems, fileId, overview, keyPoints, sections, dataPoints, answers, lockedCount, context, qaHistory, saveHistory, persistSessionHistory, updateLocalHistoryItem]);

  const handleAddQuiz = useCallback((
    type: "mcq" | "tf",
    config: { count: number; difficulty: string; choicesCount: number },
  ) => {
    addMoreQuiz(type, config, {
      setError: handleErrorText,
      setLoading,
      setLoadingText,
      onUpdated: persistQuizUpdate,
    });
  }, [addMoreQuiz, persistQuizUpdate, handleErrorText]);

  const handleAskQA = useCallback(() => {
    askQA(context, {
      setError: handleErrorText,
      setLoading,
      onNotice: (msg) => showToast(msg, "error"),
      onAnswered: async (newHistory) => {
        if (!canUseProtectedApi(!!currentUser)) return;
        if (currentHistoryId) {
          const payload = buildHistoryPayload({
            pdf, currentHistoryId, historyItems, fileId,
            overview, keyPoints, sections, dataPoints,
            questions: questions, answers: answers,
            score: score !== null ? score : -1,
            content: context, qaHistory: newHistory,
          });
          await saveHistory.mutateAsync({ currentHistoryId, payload });
          updateLocalHistoryItem({ qa_history: newHistory, answers: answers });
        } else {
          await persistSessionHistory({ qaHistory: newHistory, score: score !== null ? score : -1 });
        }
      },
    });
  }, [askQA, context, currentUser, currentHistoryId, pdf, historyItems, fileId, overview, keyPoints, sections, dataPoints, questions, answers, score, saveHistory, persistSessionHistory, updateLocalHistoryItem]);

  const handleSubmitQuiz = useCallback(() => {
    submitQuiz(async (correct) => {
      if (!canUseProtectedApi(!!currentUser)) return;
      if (currentHistoryId) {
        const payload = buildHistoryPayload({
          pdf, currentHistoryId, historyItems, fileId,
          overview, keyPoints, sections, dataPoints,
          questions: questions, answers: answers,
          score: correct, content: context, qaHistory: qaHistory,
          manualFallback: "เนื้อหาพิมพ์เอง",
        });
        await saveHistory.mutateAsync({ currentHistoryId, payload });
        updateLocalHistoryItem({
          score: correct,
          totalQuestions: questions.length,
          answers: answers,
          lockedCount: questions.length,
        });
      } else {
        await persistSessionHistory({ score: correct, manualFallback: "เนื้อหาพิมพ์เอง" });
      }
    });
  }, [submitQuiz, currentUser, currentHistoryId, pdf, historyItems, fileId, overview, keyPoints, sections, dataPoints, context, qaHistory, questions, answers, saveHistory, persistSessionHistory, updateLocalHistoryItem]);

  useEffect(() => {
    if (!currentUser && !isDemoAuthEnabled()) {
      handleNewSession();
    }
  }, [currentUser, handleNewSession]);

  const summarize = async () => {
    setIsLanding(false);
    if (!context) return;
    if (!canUseProtectedApi(!!currentUser)) { setAuthOpen(true); return; }
    if (!pdf) { setFileId("manual"); firstLoadRef.current = true; await loadNote("manual"); }

    const isUpdating = !!currentHistoryId;
    const prevQuestions = quiz.questions;
    const prevAnswers = quiz.answers;
    const prevScore = quiz.score;
    const prevLockedCount = quiz.lockedCount;

    setLoading(true);
    const parts = Math.ceil(context.length / 12000);
    setLoadingText(
      parts > 1
        ? `กำลังวิเคราะห์เนื้อหา ${parts} ส่วน… เอกสารยาวอาจใช้เวลาสักครู่`
        : "กำลังวิเคราะห์และสรุปเนื้อหา"
    );
    setError(null);
    setOverview("");
    setKeyPoints([]);
    setSections([]);
    setDataPoints([]);

    if (!isUpdating) {
      resetQuiz();
      resetQA();
    }

    try {
      const raw = await apiFetch<unknown>("/summarize", {
        method: "POST",
        auth: authHeader,
        json: { context },
      });
      const data = parseApi(SummarizeResponseSchema, raw, "summarize");
      setOverview(typeof data.overview === "string" ? data.overview : "");
      setKeyPoints(Array.isArray(data.key_points) ? data.key_points.filter((x): x is string => typeof x === "string") : []);
      setSections(Array.isArray(data.sections) ? (data.sections.filter((x): x is Section => !!x && typeof x === "object") as Section[]) : []);
      setDataPoints(Array.isArray(data.data_points) ? (data.data_points.filter((x): x is DataPoint => !!x && typeof x === "object") as DataPoint[]) : []);
      await ensureTopics();

      if (canUseProtectedApi(!!currentUser)) {
        const payload = buildHistoryPayload({
          pdf,
          currentHistoryId,
          historyItems,
          fileId,
          overview: typeof data.overview === "string" ? data.overview : "",
          keyPoints: Array.isArray(data.key_points) ? data.key_points : [],
          sections: Array.isArray(data.sections) ? data.sections : [],
          dataPoints: Array.isArray(data.data_points) ? data.data_points : [],
          questions: isUpdating ? prevQuestions : [],
          answers: isUpdating ? prevAnswers : {},
          score: isUpdating ? (prevScore ?? -1) : -1,
          content: context,
          qaHistory: qaHistory,
        });
        if (currentHistoryId) {
          await saveHistory.mutateAsync({ currentHistoryId, payload });
          updateLocalHistoryItem({ ...payload, lockedCount: prevLockedCount });
        } else {
          const saved = await saveHistory.mutateAsync({ currentHistoryId: null, payload });
          if (saved?.id) {
            setCurrentHistoryId(saved.id);
            await autosaveNote(saved.id, note);
            setFileId(saved.id);
          }
        }
      }
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
      setLoadingText(""); // 🟢 ปิด Loading Overlay
    }
  };

  const mcqCount = countByType("mcq");
  const tfCount = countByType("tf");

  useEffect(() => {
    if (!authReady) return;
    firstLoadRef.current = true;
    loadNote(fileId);
  }, [authReady, fileId, loadNote]);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans" onMouseMove={handleMouseMove}>
      <style jsx>{`
        @keyframes drift {
          0% { background-position: 0 0; }
          100% { background-position: 40px 40px; }
        }
        .animate-grid {
          animation: drift 3s linear infinite;
        }
      `}</style>

      <header className="border-b border-zinc-800 bg-zinc-950/85 backdrop-blur-md sticky top-0 z-50 shrink-0">
        <div className="mx-auto max-w-full px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">

            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
              title="เปิด/ปิดแถบประวัติ"
              style={{ display: currentUser ? 'block' : 'none' }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
            </button>

            <h1
              onClick={handleNewSession}
              className="text-2xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent cursor-pointer hover:opacity-80 transition"
            >
              EduGen
            </h1>
          </div>


          <div className="flex items-center gap-3">
            {/* 🟢 แสดงคะแนน */}
            {!isLanding && isOverallSubmitted && (<Label>คะแนน: <b className="text-emerald-400">{score}</b></Label>)}

            {/* 🟢 ปุ่ม ออก (Logout) และ เข้าสู่ระบบ (Login) ให้สวยงามขึ้น */}
            {currentUser ? (
              <div className="flex items-center gap-3 pr-2 sm:border-r border-zinc-800">
                <span className="hidden sm:inline max-w-[150px] truncate text-xs font-medium text-zinc-400">
                  {currentUser.email}
                </span>
                <button
                  onClick={handleLogout}
                  className="group flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800/40 border border-zinc-700/50 text-zinc-300 hover:bg-red-500/10 hover:border-red-500/30 hover:text-red-400 transition-all text-sm font-medium"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:translate-x-0.5 transition-transform"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                  ออก
                </button>
              </div>
            ) : (
              <button
                onClick={() => { setAuthOpen(true); }}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 hover:bg-indigo-500/20 hover:text-indigo-300 transition-all text-sm font-medium"
              >
                เข้าสู่ระบบ
              </button>
            )}

            {/* ปุ่มคลัง และ แชทใหม่ */}
            {currentUser && <PrimaryBtn onClick={() => bank.openLibrary()} className="bg-zinc-800 hover:bg-zinc-700 text-sm">คลัง</PrimaryBtn>}

            {!isLanding && currentUser && (
              <PrimaryBtn onClick={handleNewSession} className="bg-emerald-600 hover:bg-emerald-500 text-sm">
                แชทใหม่
              </PrimaryBtn>
            )}
          </div>


        </div>
      </header>

      <div className="flex flex-1 w-full h-[calc(100vh-73px)] overflow-hidden relative">

        {currentUser && (
          <aside
            className={`
              border-r border-zinc-800 bg-zinc-950/50 flex-shrink-0 transition-all duration-300 ease-in-out relative z-20
              ${isSidebarOpen ? 'w-72 translate-x-0' : 'w-0 -translate-x-full opacity-0 overflow-hidden'}
            `}
          >
            <div className="h-full overflow-hidden w-72">
              <HistorySidebar
                items={historyItems}
                onSelect={loadFromHistory}
                onDelete={deleteHistory}
                onRename={renameHistory}
                activeId={currentHistoryId}
              />
            </div>
          </aside>
        )}

        <main className="flex-1 flex flex-col min-w-0 overflow-y-auto transition-all duration-500 relative z-10">

          {isLanding ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center animate-in fade-in zoom-in duration-500 relative overflow-hidden">

              <div
                className="pointer-events-none fixed inset-0 z-0 animate-grid"
                style={{
                  backgroundImage: `
                    radial-gradient(600px at ${mousePosition.x}px ${mousePosition.y}px, rgba(29, 78, 216, 0.15), transparent 80%),
                    linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px),
                    linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px)
                  `,
                  backgroundSize: '40px 40px, 40px 40px, 40px 40px'
                }}
              />

              <div className="relative z-10 mb-8 space-y-4">
                <h1 className="text-5xl md:text-6xl font-extrabold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent pb-2 drop-shadow-2xl h-20 flex items-center justify-center">
                  {welcomeText}<span className="animate-pulse text-white">|</span>
                </h1>
                <p className="text-zinc-400 text-lg">
                  อัปโหลด PDF หรือพิมพ์เนื้อหาเพื่อเริ่มสรุปและสร้างข้อสอบได้ทันที
                </p>
              </div>

              <div className="w-full max-w-2xl bg-zinc-900/80 border border-zinc-700 rounded-3xl p-4 shadow-2xl backdrop-blur-sm relative z-10 group focus-within:border-indigo-500 transition-colors">
                <textarea
                  placeholder="พิมพ์เนื้อหาที่ต้องการสรุป หรือถามคำถาม..."
                  className="w-full h-32 bg-transparent border-0 outline-none text-lg resize-none placeholder-zinc-500 text-zinc-100"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); summarize(); } }}
                />

                <div className="flex justify-between items-center mt-2">
                  <div className="flex gap-2">
                    <PdfUploader onUpload={uploadPdf} />
                  </div>
                  <button
                    onClick={summarize}
                    disabled={!text.trim()}
                    className="bg-white text-black p-3 rounded-full hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="px-6 py-6 space-y-8 w-full max-w-5xl mx-auto animate-in slide-in-from-bottom-4 duration-500">

              <div className="relative group rounded-3xl border border-zinc-800/80 bg-zinc-950/60 backdrop-blur-xl shadow-2xl overflow-hidden transition-all duration-500 hover:border-zinc-700/80">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500/40 via-purple-500/40 to-transparent opacity-40 group-hover:opacity-100 transition-opacity duration-500"></div>

                <div className="p-2 sm:p-4">
                  <textarea
                    placeholder="พิมพ์เนื้อหาเพิ่มเติมเพื่อเริ่มสรุป หรืออัปโหลดไฟล์ PDF ด้านล่าง..."
                    className="w-full h-36 bg-transparent border-0 px-4 py-2 text-zinc-100 placeholder-zinc-600 focus:ring-0 outline-none resize-none leading-relaxed text-base md:text-lg custom-scrollbar"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                  />
                </div>

                {/* --- Control Bar --- */}
                <div className="bg-zinc-900/80 px-4 sm:px-6 py-4 flex flex-col lg:flex-row items-center justify-between gap-4 border-t border-zinc-800/80">

                  {/* --- ส่วนซ้าย: ชื่อไฟล์ (ปรับปรุง: ล็อกพื้นที่และตัดคำ) --- */}
                  <div className="w-full lg:max-w-[30%] xl:max-w-[40%] flex justify-center lg:justify-start overflow-hidden">
                    {(pdf || (fileId && fileId !== "manual")) ? (
                      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-sm min-w-0 max-w-full">
                        <svg className="shrink-0" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>

                        {/* จุดสำคัญ: ใช้ truncate เพื่อตัดคำเป็น ... และใส่ min-w-0 เพื่อให้ตัดคำได้จริง */}
                        <span className="font-medium truncate block">
                          {pdf ? pdf.name : (historyItems.find(i => i.id === currentHistoryId)?.fileName || fileId)}
                        </span>
                      </div>
                    ) : (
                      <div className="text-zinc-500 text-sm font-medium px-2 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-zinc-600"></span>
                        โmovedข้อความ (Manual)
                      </div>
                    )}
                  </div>

                  {/* --- ส่วนขวา: ปุ่มเครื่องมือ (ปรับปรุง: เพิ่ม shrink-0 เพื่อห้ามปุ่มเล็กลง) --- */}
                  <div className="w-full lg:w-auto flex flex-wrap items-center justify-center lg:justify-end gap-2 sm:gap-3 shrink-0">

                    <button
                      onClick={summarize}
                      disabled={loading}
                      className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-bold text-white transition-all duration-300 disabled:opacity-50 bg-gradient-to-br from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 shadow-sm flex-1 sm:flex-none whitespace-nowrap"
                    >
                      สรุปเนื้อหา
                    </button>

                    {currentUser && (
                      <button
                        onClick={() => setNoteOpen(true)}
                        className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all duration-300 disabled:opacity-50 bg-zinc-800/60 border border-zinc-700/60 text-zinc-300 hover:bg-zinc-700 hover:text-white flex-1 sm:flex-none whitespace-nowrap"
                      >
                        โน้ต
                      </button>
                    )}

                    <div className="hidden sm:block w-px h-6 bg-zinc-700/50 mx-1 shrink-0"></div>

                    <QuizToolbar
                      mcqCount={mcqCount}
                      tfCount={tfCount}
                      loading={loading}
                      topicCount={quiz.topicsRef.current.length}
                      onAdd={handleAddQuiz}
                    />

                  </div>
                </div>

              </div>

              <QASection
                qaInput={qaInput}
                qaHistory={qaHistory}
                loading={loading}
                onInputChange={setQaInput}
                onAsk={handleAskQA}
              />

              {error && <Card className="border-red-700/50 bg-red-900/20 text-red-200">{error}</Card>}

              <SummarySection overview={overview} keyPoints={keyPoints} sections={sections} dataPoints={dataPoints} />

              <QuizSection
                questions={questions}
                answers={answers}
                score={score}
                lockedCount={lockedCount}
                isOverallSubmitted={isOverallSubmitted}
                isAllAnswered={isAllAnswered}
                showSaveButton={!!currentUser}
                onAnswerChange={(idx, val) => handleAnswerChange(idx, val, currentHistoryId, setHistoryItems)}
                onSubmit={handleSubmitQuiz}
                onSaveQuestion={(idx) => bank.openSaveQuestion(idx)}
              />
            </div>
          )}
        </main>
      </div>

      {/* 🟢 Premium Loading Overlay */}
      {loadingText && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300"></div>
          <div className="relative bg-zinc-900/90 border border-zinc-700/50 shadow-[0_0_50px_rgba(99,102,241,0.15)] rounded-3xl p-8 flex flex-col items-center gap-6 animate-in zoom-in-95 fade-in duration-300 min-w-[320px] max-w-sm text-center">
            <div className="relative flex items-center justify-center w-20 h-20">
              {/* Outer spinning ring */}
              <div className="absolute inset-0 rounded-full border-[3px] border-zinc-800"></div>
              <div className="absolute inset-0 rounded-full border-[3px] border-indigo-500 border-t-transparent animate-spin"></div>
              {/* Inner glowing element */}
              <div className="w-8 h-8 bg-indigo-500/20 rounded-full blur-md animate-pulse"></div>
              <svg className="absolute text-indigo-400 w-8 h-8 animate-pulse" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v4"></path><path d="M12 18v4"></path><path d="M4.93 4.93l2.83 2.83"></path><path d="M16.24 16.24l2.83 2.83"></path><path d="M2 12h4"></path><path d="M18 12h4"></path><path d="M4.93 19.07l2.83-2.83"></path><path d="M16.24 7.76l2.83-2.83"></path></svg>
            </div>
            <div className="space-y-2">
              <h3 className="text-zinc-100 font-bold text-lg tracking-wide">{loadingText}</h3>
              <p className="text-zinc-500 text-sm">กรุณารอสักครู่ ระบบกำลังประมวลผล...</p>
            </div>
          </div>
        </div>
      )}

      <Modal open={noteOpen} onClose={() => setNoteOpen(false)} title="โน้ตของฉัน" rightInfo={<>{noteStatus === "saving" && "กำลังบันทึก…"}{noteStatus === "saved" && (noteUpdatedAt ? `บันทึกล่าสุด: ${new Date(noteUpdatedAt).toLocaleString()}` : "บันทึกแล้ว")}{noteStatus === "error" && <span className="text-red-300">บันทึกล้มเหลว</span>}</>}>
        <textarea placeholder="จดสรุป/ประเด็นสำคัญ/ข้อสงสัย… (บันทึกอัตโนมัติ)" className="w-full h-60 rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-3 outline-none focus:border-indigo-500" value={note} onChange={(e) => setNote(e.target.value)} />
        <div className="mt-2 text-xs text-zinc-500">* ระบบบันทึกอัตโนมัติและผูกโน้ตกับไฟล์ที่คุณใช้งานอยู่</div>
      </Modal>

      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />

      <BankPanel
        {...bank}
        questions={questions}
      />

      <PromptModal
        open={!!renameHistoryTarget}
        title="ตั้งชื่อประวัติใหม่"
        label="ชื่อประวัติ"
        defaultValue={renameHistoryTarget?.name ?? ""}
        onCancel={() => setRenameHistoryTarget(null)}
        onConfirm={async (newName) => {
          if (!renameHistoryTarget) return;
          const target = renameHistoryTarget;
          setRenameHistoryTarget(null);
          if (newName === target.name) return;
          try {
            await renameHistoryMutation.mutateAsync({ id: target.id, name: newName });
            showToast("เปลี่ยนชื่อแล้ว");
          } catch {
            showToast("เปลี่ยนชื่อไม่สำเร็จ", "error");
          }
        }}
      />

      <LoginRequiredModal
        open={loginRequired}
        onClose={() => setLoginRequired(false)}
        onLogin={() => { setLoginRequired(false); setAuthOpen(true); }}
      />

      <ConfirmModal
        open={!!deleteHistoryTarget}
        title="ลบประวัติ"
        message="ต้องการลบประวัตินี้ใช่หรือไม่? เมื่อลบแล้วจะไม่สามารถกู้คืนได้"
        confirmText="ลบ"
        danger
        onCancel={() => setDeleteHistoryTarget(null)}
        onConfirm={async () => {
          const id = deleteHistoryTarget;
          if (!id) return;
          setDeleteHistoryTarget(null);
          try {
            await deleteHistoryMutation.mutateAsync(id);
            if (currentHistoryId === id) handleNewSession();
            showToast("ลบประวัติแล้ว");
          } catch {
            showToast("ลบไม่สำเร็จ", "error");
          }
        }}
      />
    </div>
  );
}