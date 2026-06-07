// ===== API Response Types =====

export interface Session {
  session_id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
}

export interface Message {
  id?: number;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  confidence?: number;
  timestamp?: string;
  isStreaming?: boolean;
}

export interface Source {
  source: string;
  page: number | string;
  score: number;
  content: string;
}

export interface Document {
  id: number;
  file_name: string;
  status: "ready" | "processing" | "error";
  chunks_count: number;
  file_size: number;
  uploaded_at: string;
  error_message?: string;
}

export interface VectorDbStats {
  total_documents: number;
  total_chunks: number;
}

export interface QuizQuestion {
  id?: number;
  type: "choice" | "fill" | "short_answer";
  question: string;
  options?: string[];
  answer?: string;
  explanation?: string;
  difficulty?: string;
  topic?: string;
}

export interface Flashcard {
  front: string;
  back: string;
  topic?: string;
}

export interface CompareResult {
  similarities: string[];
  differences: string[];
  summary: string;
}

export interface ReadingProgress {
  file_name: string;
  current_page: number;
  total_pages: number;
  is_finished: boolean;
}

export interface Bookmark {
  id: number;
  file_name: string;
  page_number: number;
  title?: string;
  note?: string;
  created_at?: string;
}

export interface Tag {
  id: number;
  name: string;
  color: string;
}

export interface Favorite {
  id: number;
  content: string;
  question?: string;
  created_at?: string;
}

export interface LearningProgress {
  total_questions: number;
  avg_confidence: number;
  knowledge_gaps: { topic: string; question_count: number }[];
}

export interface WeakTopic {
  topic: string;
  question_count: number;
}

export interface RateLimitInfo {
  limit: number;
  window_seconds: number;
  remaining: number;
  used: number;
}

// ===== Chat SSE Types =====

export interface ChatChunk {
  type: "token" | "sources" | "confidence" | "error" | "done" | "result";
  content?: string;
  data?: string | { sources?: Source[]; confidence?: number; [key: string]: unknown };
  sources?: Source[];
  confidence?: number;
}

// ===== Mindmap Types =====

export interface MindmapNode {
  id: string;
  label: string;
  parentId: string | null;
}

export interface GenerateResponse {
  status: "success" | "error";
  type: "mindmap" | "notes";
  content: string;
  nodes?: MindmapNode[];
  mermaid_code?: string;
  message: string;
}

export interface SavedMindmap {
  id: number;
  title: string;
  output_type: "mindmap" | "notes";
  content?: string;
  mermaid_code?: string;
  file_names?: string[];
  created_at?: string;
}

export interface SavedQuiz {
  id: number;
  title: string;
  questions: QuizQuestion[];
  score_correct: number;
  score_total: number;
  difficulty: string;
  file_names?: string[];
  created_at?: string;
}

export interface SavedFlashcardSet {
  id: number;
  title: string;
  cards: Flashcard[];
  file_names?: string[];
  created_at?: string;
}

// ===== Settings =====

export interface LlmSettings {
  provider: "local" | "cloud";
  local: { base_url: string; model: string };
  cloud: { base_url: string; api_key: string; model: string; api_format: string };
}

// ===== Panel State =====

export type PanelType = "mindmap" | "quiz" | "flashcard" | "stats" | "compare" | "settings" | null;
