export type QuizItem = {
  type: "mcq" | "tf";
  question: string;
  choices?: string[];
  answer: string;
  explain?: string;
};

export type Section = {
  title: string;
  summary: string;
};

export type DataPoint = {
  label: string;
  value: string;
  unit?: string;
};

export type QAPair = {
  question: string;
  answer: string;
  source?: string;
};

export type BankQuestion = {
  id: number;
  type: "mcq" | "tf";
  question: string;
  choices?: string[] | null;
  answer: string;
  explain?: string;
  topic?: string;
};

export type QuizSet = {
  id: number;
  title: string;
  question_ids: number[];
  created_at: string;
  updated_at: string;
};

export type HistoryItem = {
  id: string;
  fileName: string;
  score: number;
  totalQuestions: number;
  timestamp: string;
  questions: QuizItem[];
  answers: Record<string, string>;
  overview: string;
  keyPoints?: string[];
  sections?: Section[];
  dataPoints?: DataPoint[];
  content?: string;
  qa_history?: QAPair[];
  lockedCount?: number;
};