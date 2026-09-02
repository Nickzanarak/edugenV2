import { useState, useEffect } from "react";
import type { QuizItem, BankQuestion } from "../../types";
import type { useBank } from "../../hooks/useBank";
import { idxToLetter } from "../../utils/helpers";
import { Modal } from "../ui/Modal";
import { PrimaryBtn } from "../ui/PrimaryBtn";
import { useToast } from "../ui/Toast";
import { PromptModal } from "../ui/PromptModal";
import { ConfirmModal } from "../ui/ConfirmModal";
import { ExportOptionsModal } from "../ui/ExportOptionsModal";

type BankState = ReturnType<typeof useBank>;

type Props = BankState & {
  questions: QuizItem[];
};

const MIN_CHOICES = 4;
const MAX_CHOICES = 6;

function EditQuestionRow({
  originalQ, index, onRemove, onSave
}: {
  originalQ: BankQuestion;
  index: number;
  onRemove: () => void;
  onSave: (updatedQ: BankQuestion) => Promise<void>;
}) {
  const { showToast } = useToast();
  const [q, setQ] = useState(originalQ);

  useEffect(() => {
    setQ(originalQ);
  }, [originalQ]);

  const isMcq = q.type === "mcq";
  const choices = q.choices ?? [];

  // ลบตัวเลือกช่องที่ i ออก แล้วเลื่อนตัวอักษรใหม่ + จัดการเฉลย
  const removeChoice = (i: number) => {
    if (choices.length <= MIN_CHOICES) return; // กันลบต่ำกว่า 4
    const arr = choices.filter((_, idx) => idx !== i);
    const ansIdx = idxToLetter.indexOf(q.answer);
    let newAns = q.answer;
    if (ansIdx === i) {
      newAns = ""; // ลบช่องที่เป็นเฉลย → เฉลยว่าง
    } else if (ansIdx > i) {
      newAns = idxToLetter[ansIdx - 1]; // เฉลยอยู่หลังช่องที่ลบ → เลื่อนขึ้น 1
    }
    setQ({ ...q, choices: arr, answer: newAns });
  };

  // เพิ่มตัวเลือกใหม่ต่อท้าย (สูงสุด 6 ช่อง)
  const addChoice = () => {
    if (choices.length >= MAX_CHOICES) return;
    setQ({ ...q, choices: [...choices, ""] });
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3 text-sm space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <label className="block text-sm text-zinc-400 mb-1">ข้อที่ {index + 1}</label>
          <input
            className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-2 font-medium text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
            value={q.question}
            onChange={(e) => setQ({ ...q, question: e.target.value })}
            placeholder="พิมพ์คำถาม…"
          />
        </div>
        <PrimaryBtn className="bg-red-700 hover:bg-red-600 shrink-0 self-start" onClick={onRemove}>
          ลบออกจากชุด
        </PrimaryBtn>
      </div>
      {isMcq ? (
        <div className="space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {choices.map((c, i) => (
              <div key={i} className="relative group/choice">
                <input
                  className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-2 pr-9"
                  value={c ?? ""}
                  onChange={(e) => {
                    const arr = [...choices];
                    arr[i] = e.target.value;
                    setQ({ ...q, choices: arr });
                  }}
                  placeholder={`ช้อยส์ ${idxToLetter[i]}`}
                />
                {choices.length > MIN_CHOICES && (
                  <button
                    type="button"
                    onClick={() => removeChoice(i)}
                    title="ลบตัวเลือกนี้"
                    className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-lg flex items-center justify-center text-zinc-500 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {choices.length < MAX_CHOICES && (
              <button
                type="button"
                onClick={addChoice}
                className="text-xs px-3 py-2 rounded-xl bg-indigo-600/10 text-indigo-300 hover:bg-indigo-600/20 border border-indigo-500/20 transition"
              >
                + เพิ่มตัวเลือก
              </button>
            )}
            <span className="text-sm text-zinc-400 shrink-0">เฉลย:</span>
            <select
              className={`rounded-xl bg-zinc-900 border px-3 py-2 ${q.answer ? "border-zinc-800" : "border-amber-500/50 text-amber-400"}`}
              value={q.answer}
              onChange={(e) => setQ({ ...q, answer: e.target.value })}
            >
              <option value="">— ยังไม่เลือก —</option>
              {idxToLetter.slice(0, choices.length).map((l) => (<option key={l} value={l}>{`เฉลย ${l}`}</option>))}
            </select>
          </div>
        </div>
      ) : (
        <div className="flex gap-3">
          <label className="flex items-center gap-2">
            <input type="radio" name={`tf-${q.id}`} checked={q.answer === "true"} onChange={() => setQ({ ...q, answer: "true" })} /> จริง
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name={`tf-${q.id}`} checked={q.answer === "false"} onChange={() => setQ({ ...q, answer: "false" })} /> เท็จ
          </label>
        </div>
      )}
      <input
        className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-2"
        value={q.explain ?? ""}
        onChange={(e) => setQ({ ...q, explain: e.target.value })}
        placeholder="เหตุผล/คำอธิบาย…"
      />
      <div className="flex justify-end">
        <PrimaryBtn
          className="bg-emerald-700 hover:bg-emerald-600"
          onClick={async () => {
            if (isMcq && !q.answer) {
              showToast(`ข้อที่ ${index + 1} ยังไม่ได้เลือกเฉลย`, "error");
              return;
            }
            if (isMcq && choices.some((c) => !String(c ?? "").trim())) {
              showToast(`ข้อที่ ${index + 1} มีตัวเลือกที่ยังไม่ได้กรอก`, "error");
              return;
            }
            try {
              await onSave(q);
              showToast("บันทึกแล้ว");
            } catch {
              showToast("บันทึกไม่สำเร็จ", "error");
            }
          }}
        >
          บันทึกข้อนี้
        </PrimaryBtn>
      </div>
    </div>
  );
}

export function BankPanel({
  questions,
  setsOpen, setSetsOpen,
  sets,
  saveOpen, setSaveOpen,
  creatingTitle, setCreatingTitle,
  manualOpen, setManualOpen,
  manualSetId, setManualSetId,
  manualType, setManualType,
  manualQ, setManualQ,
  manualChoices, setManualChoices,
  manualAns, setManualAns,
  manualExplain, setManualExplain,
  editOpen, setEditOpen,
  bankQuestions,
  loadSets, loadBank,
  createSet, renameSet, deleteSet,
  exportSetPdf, saveQuestionToSet, updateBankQuestion,
}: Props) {
  const { showToast } = useToast();
  // popup แก้ชื่อชุด / ยืนยันลบ (ใช้แทน prompt/confirm ของเบราว์เซอร์)
  const [renameTarget, setRenameTarget] = useState<{ id: number; title: string } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; title: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [exportTarget, setExportTarget] = useState<{ id: number; title: string } | null>(null);

  /** สร้างชุดข้อสอบใหม่ — ใช้ร่วมกันทั้งปุ่มและการกด Enter
   *  เดิมเขียนแยกกัน 2 ที่ ทำให้พฤติกรรมต่างกันและไม่มีใครจับ error
   *  ล้างช่องเฉพาะตอนสำเร็จ ผู้ใช้จะได้ไม่ต้องพิมพ์ชื่อใหม่ถ้าพลาด
   */
  const handleCreateSet = async () => {
    const title = creatingTitle.trim();
    if (!title || creating) return;
    setCreating(true);
    try {
      await createSet(title);
      setCreatingTitle("");
      showToast(`สร้างชุด "${title}" แล้ว`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "สร้างชุดไม่สำเร็จ", "error");
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <Modal
        open={saveOpen.open}
        onClose={() => setSaveOpen({ open: false, qIndex: null })}
        title="บันทึกข้อสอบลงชุด"
      >
        <div className="space-y-3">
          {saveOpen.qIndex !== null && questions[saveOpen.qIndex] && (
            <div className="p-3 rounded-xl bg-zinc-800/50 border border-zinc-700/50 text-sm text-zinc-300 mb-4">
              <span className="font-semibold text-indigo-400">ข้อที่เลือก:</span> {questions[saveOpen.qIndex].question}
            </div>
          )}
          <div className="grid gap-2">
            {sets.length === 0 && (
              <div className="text-center text-zinc-500 py-4">ยังไม่มีชุดข้อสอบ (ไปสร้างที่เมนู &quot;จัดการชุดข้อสอบ&quot; ก่อน)</div>
            )}
            {sets.map((s) => (
              <button
                key={s.id}
                className="flex items-center justify-between p-3 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 transition text-left group"
                onClick={async () => {
                  if (saveOpen.qIndex === null) return;
                  const q = questions[saveOpen.qIndex];
                  try {
                    await saveQuestionToSet(s.id, q);
                    showToast(`บันทึกลงชุด "${s.title}" แล้ว`);
                    setSaveOpen({ open: false, qIndex: null });
                  } catch (e) {
                    showToast(e instanceof Error ? e.message : "บันทึกไม่สำเร็จ", "error");
                  }
                }}
              >
                <span className="font-medium">{s.title}</span>
                <span className="text-xs bg-zinc-800 px-2 py-1 rounded text-zinc-400 group-hover:bg-zinc-700">
                  {s.question_ids.length} ข้อ
                </span>
              </button>
            ))}
          </div>
        </div>
      </Modal>

      <Modal open={setsOpen} onClose={() => setSetsOpen(false)} title="จัดการชุดข้อสอบ">
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              className="flex-1 rounded-2xl bg-zinc-900/50 border border-zinc-800 px-4 py-3 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
              placeholder="ตั้งชื่อชุดข้อสอบใหม่…"
              value={creatingTitle}
              onChange={(e) => setCreatingTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreateSet();
              }}
              disabled={creating}
            />
            <button
              onClick={handleCreateSet}
              disabled={creating || !creatingTitle.trim()}
              className="rounded-2xl bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg shadow-indigo-500/25 hover:from-indigo-500 hover:to-purple-500 disabled:from-zinc-800 disabled:to-zinc-800 disabled:text-zinc-600 disabled:shadow-none transition-all whitespace-nowrap flex items-center justify-center gap-2"
            >
              {creating ? "กำลังสร้าง…" : "สร้างชุดใหม่"}
            </button>
          </div>

          {sets.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 border border-dashed border-zinc-800 rounded-2xl bg-zinc-900/20">
              ยังไม่มีชุดข้อสอบ — ลองสร้างชุดแรกดูสิ
            </div>
          ) : (
            <ul className="space-y-3">
              {sets.map((s) => (
                <li key={s.id} className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-4 hover:border-zinc-700/80 hover:bg-zinc-800/40 transition-all flex flex-col xl:flex-row xl:items-center justify-between gap-4 group">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="font-semibold text-lg text-zinc-200 truncate">{s.title}</span>
                    <span className="shrink-0 px-2.5 py-1.5 rounded-lg bg-zinc-800/80 border border-zinc-700 text-xs text-zinc-400 font-medium flex items-center gap-1">
                      <span>{s.question_ids.length}</span> ข้อ
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    <button
                      className="text-xs px-3 py-2 rounded-xl bg-zinc-800/50 text-zinc-300 hover:bg-zinc-700 hover:text-white transition border border-zinc-700/50"
                      onClick={() => setRenameTarget({ id: s.id, title: s.title })}
                    >
                      แก้ชื่อ
                    </button>
                    <button
                      className="text-xs px-3 py-2 rounded-xl bg-sky-600/10 text-sky-400 hover:bg-sky-600/20 hover:text-sky-300 transition border border-sky-500/20"
                      onClick={async () => { await loadBank(); setEditOpen({ open: true, set: s }); }}
                    >
                      แก้รายการ
                    </button>
                    <button
                      className="text-xs px-3 py-2 rounded-xl bg-purple-600/10 text-purple-400 hover:bg-purple-600/20 hover:text-purple-300 transition border border-purple-500/20"
                      onClick={() => { setManualSetId(s.id); setManualOpen(true); }}
                    >
                      เพิ่มข้อเอง
                    </button>
                    <button
                      className="text-xs px-3 py-2 rounded-xl bg-emerald-600/10 text-emerald-400 hover:bg-emerald-600/20 hover:text-emerald-300 transition border border-emerald-500/20"
                      onClick={() => setExportTarget({ id: s.id, title: s.title })}
                    >
                      ส่งออก PDF
                    </button>
                    <button
                      className="text-xs px-3 py-2 rounded-xl bg-red-600/10 text-red-400 hover:bg-red-600/20 hover:text-red-300 transition border border-red-500/20"
                      onClick={() => setDeleteTarget({ id: s.id, title: s.title })}
                    >
                      ลบ
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Modal>

      <Modal open={manualOpen} onClose={() => setManualOpen(false)} title="เพิ่มข้อสอบเองลงชุด">
        <div className="space-y-3">
          <div className="flex gap-2">
            <select className="rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-2" value={manualSetId ?? ""} onChange={(e) => setManualSetId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">เลือกชุดที่จะเพิ่ม…</option>
              {sets.map((s) => (<option key={s.id} value={s.id}>{s.title} ({s.question_ids.length} ข้อ)</option>))}
            </select>
            <select className="rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-2" value={manualType} onChange={(e) => setManualType(e.target.value as "mcq" | "tf")}>
              <option value="mcq">แบบปรนัย</option>
              <option value="tf">แบบถูกผิด</option>
            </select>
          </div>
          <textarea className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-2" placeholder="พิมพ์คำถาม…" value={manualQ} onChange={(e) => setManualQ(e.target.value)} />
          {manualType === "mcq" ? (
            <div className="space-y-2">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {manualChoices.map((c, i) => (
                  <div key={i} className="relative">
                    <input
                      className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-2 pr-9"
                      placeholder={`ช้อยส์ ${idxToLetter[i]}`}
                      value={c}
                      onChange={(e) => { const clone = manualChoices.slice(); clone[i] = e.target.value; setManualChoices(clone); }}
                    />
                    {manualChoices.length > MIN_CHOICES && (
                      <button
                        type="button"
                        title="ลบตัวเลือกนี้"
                        onClick={() => {
                          const arr = manualChoices.filter((_, idx) => idx !== i);
                          const ansIdx = idxToLetter.indexOf(manualAns);
                          if (ansIdx === i) setManualAns("");
                          else if (ansIdx > i) setManualAns(idxToLetter[ansIdx - 1]);
                          setManualChoices(arr);
                        }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-lg flex items-center justify-center text-zinc-500 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {manualChoices.length < MAX_CHOICES && (
                  <button
                    type="button"
                    onClick={() => setManualChoices([...manualChoices, ""])}
                    className="text-xs px-3 py-2 rounded-xl bg-indigo-600/10 text-indigo-300 hover:bg-indigo-600/20 border border-indigo-500/20 transition"
                  >
                    + เพิ่มตัวเลือก
                  </button>
                )}
                <span className="text-sm text-zinc-400 shrink-0">เฉลย:</span>
                <select
                  className={`rounded-xl bg-zinc-900 border px-3 py-2 ${manualAns ? "border-zinc-800" : "border-amber-500/50 text-amber-400"}`}
                  value={manualAns}
                  onChange={(e) => setManualAns(e.target.value)}
                >
                  <option value="">— ยังไม่เลือก —</option>
                  {idxToLetter.slice(0, manualChoices.length).map((l) => (<option key={l} value={l}>{`เฉลย ${l}`}</option>))}
                </select>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" name="tfans" value="true" checked={manualAns === "true"} onChange={() => setManualAns("true")} /> จริง (true)
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" name="tfans" value="false" checked={manualAns === "false"} onChange={() => setManualAns("false")} /> เท็จ (false)
              </label>
            </div>
          )}
          <input className="w-full rounded-xl bg-zinc-900 border border-zinc-800 px-3 py-2" placeholder="เหตุผล/คำอธิบาย (ถ้ามี)…" value={manualExplain} onChange={(e) => setManualExplain(e.target.value)} />
          <div className="flex justify-end">
            <PrimaryBtn
              onClick={async () => {
                if (!manualSetId) { showToast("กรุณาเลือกชุดที่จะเพิ่มก่อน", "error"); return; }
                if (!manualQ.trim()) { showToast("กรุณาพิมพ์คำถาม", "error"); return; }
                if (manualType === "mcq" && !manualAns) { showToast("กรุณาเลือกเฉลยก่อนบันทึก", "error"); return; }
                if (manualType === "mcq" && manualChoices.some((c) => !c.trim())) {
                  showToast("กรุณากรอกตัวเลือกให้ครบทุกช่อง", "error"); return;
                }
                const qi: QuizItem = manualType === "mcq"
                  ? { type: "mcq", question: manualQ.trim(), choices: manualChoices.map((x) => x.trim()), answer: manualAns, explain: manualExplain.trim() }
                  : { type: "tf", question: manualQ.trim(), answer: manualAns.toLowerCase() === "true" ? "true" : "false", explain: manualExplain.trim() };
                try {
                  await loadBank();
                  await saveQuestionToSet(manualSetId, qi);
                  await loadSets();
                  setManualQ("");
                  setManualChoices(["", "", "", ""]);
                  setManualAns(manualType === "mcq" ? "ก" : "true");
                  setManualExplain("");
                  showToast("เพิ่มข้อสอบแล้ว");
                } catch (e) {
                  showToast(e instanceof Error ? e.message : "เกิดข้อผิดพลาดในการบันทึก", "error");
                }
              }}
            >
              เพิ่มลงชุด
            </PrimaryBtn>
          </div>
        </div>
      </Modal>

      <Modal
        open={editOpen.open}
        onClose={() => setEditOpen({ open: false, set: null })}
        title={`แก้รายการในชุด: ${editOpen.set?.title ?? ""}`}
      >
        {!editOpen.set ? (
          <div className="text-sm text-zinc-400">ไม่พบชุด</div>
        ) : (
          <div className="space-y-3">
            {(editOpen.set?.question_ids ?? []).length === 0 && (
              <div className="text-sm text-zinc-400">ยังไม่มีข้อสอบในชุดนี้</div>
            )}
            {(editOpen.set?.question_ids ?? []).map((qid, index) => {
              const q = bankQuestions.find((b) => b.id === qid);
              if (!q) {
                return (
                  <div key={qid} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3 text-sm">
                    <div className="flex items-center justify-between">
                      <div className="text-red-300">ไม่พบข้อสอบ ID {qid}</div>
                      <PrimaryBtn
                        className="bg-red-700 hover:bg-red-600"
                        onClick={async () => {
                          if (!editOpen.set) return;
                          const ids = editOpen.set.question_ids.filter((id) => id !== qid);
                          try {
                            await renameSet(editOpen.set.id, editOpen.set.title, ids);
                            await loadSets();
                            setEditOpen((e) => ({ ...e, set: { ...e.set!, question_ids: ids } }));
                            showToast("ลบออกจากชุดแล้ว");
                          } catch {
                            showToast("ลบออกจากชุดไม่สำเร็จ", "error");
                          }
                        }}
                      >
                        ลบออกจากชุด
                      </PrimaryBtn>
                    </div>
                  </div>
                );
              }

              return (
                <EditQuestionRow
                  key={qid}
                  originalQ={q}
                  index={index}
                  onRemove={async () => {
                    if (!editOpen.set) return;
                    const ids = editOpen.set.question_ids.filter((id) => id !== qid);
                    try {
                      await renameSet(editOpen.set.id, editOpen.set.title, ids);
                      await loadSets();
                      setEditOpen((e) => ({ ...e, set: { ...e.set!, question_ids: ids } }));
                      showToast("ลบออกจากชุดแล้ว");
                    } catch {
                      showToast("ลบออกจากชุดไม่สำเร็จ", "error");
                    }
                  }}
                  onSave={async (updatedQ) => {
                    await updateBankQuestion(updatedQ);
                  }}
                />
              );
            })}
          </div>
        )}
      </Modal>

      <PromptModal
        open={!!renameTarget}
        title="แก้ไขชื่อชุดข้อสอบ"
        label="ชื่อชุดข้อสอบ"
        defaultValue={renameTarget?.title ?? ""}
        onCancel={() => setRenameTarget(null)}
        onConfirm={async (name) => {
          if (!renameTarget) return;
          const target = renameTarget;
          setRenameTarget(null);
          try {
            await renameSet(target.id, name);
            showToast("เปลี่ยนชื่อแล้ว");
          } catch {
            showToast("เปลี่ยนชื่อไม่สำเร็จ", "error");
          }
        }}
      />

      <ExportOptionsModal
        open={!!exportTarget}
        setTitle={exportTarget?.title ?? ""}
        onCancel={() => setExportTarget(null)}
        onConfirm={(showAnswers) => {
          if (!exportTarget) return;
          const target = exportTarget;
          setExportTarget(null);
          exportSetPdf(
            target.id,
            // ใช้ Toast เพราะผู้ใช้อยู่ใน popup ซึ่งบังกล่อง error ของหน้าหลัก
            (msg) => showToast(msg, "error"),
            { showAnswers },
          );
        }}
      />

      <ConfirmModal
        open={!!deleteTarget}
        title="ลบชุดข้อสอบ"
        message={`ต้องการลบชุด "${deleteTarget?.title ?? ""}" ใช่หรือไม่? ข้อสอบในชุดจะไม่ถูกลบออกจากคลัง`}
        confirmText="ลบ"
        danger
        onCancel={() => setDeleteTarget(null)}
        onConfirm={async () => {
          if (!deleteTarget) return;
          const target = deleteTarget;
          setDeleteTarget(null);
          try {
            await deleteSet(target.id);
            showToast("ลบชุดแล้ว");
          } catch {
            showToast("ลบไม่สำเร็จ", "error");
          }
        }}
      />
    </>
  );
}