import { z } from "zod";

export const SectionSchema = z.object({
  title: z.string(),
  summary: z.string(),
});

export const DataPointSchema = z.object({
  label: z.string(),
  value: z.string(),
  unit: z.string().optional(),
});

export const SummarizeResponseSchema = z.object({
  overview: z.string().optional().default(""),
  key_points: z.array(z.string()).optional().default([]),
  sections: z.array(SectionSchema).optional().default([]),
  data_points: z.array(DataPointSchema).optional().default([]),
});

export const TopicsResponseSchema = z.object({
  topics: z.array(z.string()).optional().default([]),
});

export const QuizApiResponseSchema = z.object({
  questions: z.array(z.unknown()).optional().default([]),
});

export const QAResponseSchema = z.object({
  answer: z.string().optional().default(""),
});

export const HistoryItemSchema = z.object({
  id: z.string(),
  fileName: z.string(),
  score: z.number(),
  totalQuestions: z.number().optional().default(0),
  timestamp: z.string(),
  questions: z.array(z.unknown()).optional().default([]),
  answers: z.record(z.string(), z.string()).optional().default({}),
  overview: z.string().optional().default(""),
  keyPoints: z.array(z.string()).optional(),
  sections: z.array(SectionSchema).optional(),
  dataPoints: z.array(DataPointSchema).optional(),
  content: z.string().optional(),
  qa_history: z.array(z.object({ question: z.string(), answer: z.string() })).optional(),
  lockedCount: z.number().optional(),
});

export const HistoryListSchema = z.array(HistoryItemSchema);

export const BankQuestionSchema = z.object({
  id: z.number(),
  type: z.enum(["mcq", "tf"]),
  question: z.string(),
  choices: z.array(z.string()).nullable().optional(),
  answer: z.string(),
  explain: z.string().optional(),
  topic: z.string().optional(),
});

export const BankQuestionListSchema = z.array(BankQuestionSchema);

export const QuizSetSchema = z.object({
  id: z.number(),
  title: z.string(),
  question_ids: z.array(z.number()),
  created_at: z.string(),
  updated_at: z.string(),
});

export const QuizSetListSchema = z.array(QuizSetSchema);

export const PdfExtractSchema = z.object({
  text: z.string().optional().default(""),
});

export const NoteSchema = z.object({
  content: z.string().optional(),
  updated_at: z.string().optional(),
});
