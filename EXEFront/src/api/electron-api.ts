/**
 * Electron 桌面端 API 客户端
 * 与 web 版 api.ts 相同的接口，但所有请求附带 X-Client-Type: desktop header
 */

import type {
  Session,
  Message,
  Document,
  VectorDbStats,
  QuizQuestion,
  Flashcard,
  CompareResult,
  ReadingProgress,
  Bookmark,
  Tag,
  Favorite,
  LearningProgress,
  RateLimitInfo,
  ChatChunk,
  GenerateResponse,
  SavedMindmap,
  SavedQuiz,
  SavedFlashcardSet,
  LlmSettings,
  UserInfo,
  UsageLogsResponse,
  SiteMessage,
  DownloadFile,
} from "@/lib/types";
import { getToken, removeToken } from "@electron/lib/auth";

// 部署时修改此处为服务器地址，例如 "https://api.example.com"
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function isElectron(): boolean {
  return typeof window !== "undefined" && !!(window as any).electronAPI;
}

// ===== Generic fetch =====

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Client-Type": "desktop",
    ...(options?.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    removeToken();
    window.dispatchEvent(new Event("auth-change"));
    throw new Error("登录已过期，请重新登录");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ===== Auth =====

export async function login(username: string, password: string): Promise<{ token: string; username: string; role: number }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Client-Type": "desktop" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function register(username: string, password: string): Promise<{ token: string; username: string; role: number }> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Client-Type": "desktop" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ===== Health =====

export async function getStatus(): Promise<{ status: string; version: string; vector_db: VectorDbStats }> {
  return apiFetch("/api/status");
}

export async function getRateLimit(): Promise<RateLimitInfo> {
  return apiFetch("/api/rate-limit");
}

// ===== Sessions =====

export async function createSession(title = "新会话"): Promise<{ session_id: string; title: string }> {
  return apiFetch("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function getSessions(page = 1, pageSize = 50): Promise<{ sessions: Session[]; total: number }> {
  return apiFetch(`/api/sessions?page=${page}&page_size=${pageSize}`);
}

export async function getSessionHistory(sid: string): Promise<{ session_id: string; messages: Message[] }> {
  return apiFetch(`/api/sessions/${sid}`);
}

export async function deleteSession(sid: string): Promise<{ status: string }> {
  return apiFetch(`/api/sessions/${sid}`, { method: "DELETE" });
}

export async function renameSession(sid: string, title: string): Promise<{ status: string }> {
  return apiFetch(`/api/sessions/${sid}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function searchSessions(keyword: string): Promise<{ sessions: Session[] }> {
  return apiFetch(`/api/sessions/search?keyword=${encodeURIComponent(keyword)}`);
}

// ===== Chat =====

export async function chat(question: string, sessionId: string): Promise<Message> {
  return apiFetch("/api/chat", {
    method: "POST",
    body: JSON.stringify({ question, session_id: sessionId }),
  });
}

export function chatStream(
  question: string,
  sessionId: string,
  onChunk: (chunk: ChatChunk) => void,
  onError: (err: Error) => void,
  onDone: () => void
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const token = getToken();
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "X-Client-Type": "desktop",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({ question, session_id: sessionId }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        let detail = `HTTP ${res.status}`;
        try {
          const errBody = await res.json();
          if (errBody.detail) detail = errBody.detail;
        } catch {}
        throw new Error(detail);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;
          const data = trimmed.slice(6);
          if (data === "[DONE]") {
            onDone();
            return;
          }
          try {
            const chunk: ChatChunk = JSON.parse(data);
            onChunk(chunk);
          } catch {
            // skip malformed JSON
          }
        }
      }
      onDone();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError(err as Error);
      }
    }
  })();

  return () => controller.abort();
}

// ===== Documents =====

export async function getDocuments(): Promise<{ documents: Document[] }> {
  return apiFetch("/api/documents");
}

export async function deleteDocument(docId: number): Promise<{ status: string }> {
  return apiFetch(`/api/documents/${docId}`, { method: "DELETE" });
}

export async function uploadDocument(file: File, skipOcr = false): Promise<{ status: string; message: string; ocr_skipped?: boolean; ocr_skipped_pages?: number }> {
  const token = getToken();
  const formData = new FormData();
  formData.append("file", file);
  const headers: Record<string, string> = { "X-Client-Type": "desktop" };
  if (skipOcr) headers["X-Local-OCR-Done"] = "true";
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ===== 本地 OCR（仅 Electron 桌面端） =====

export interface LocalPdfOcrResult {
  pages: { content: string; page: number; source: string; file_type: string }[]
  ocr_skipped: boolean
  ocr_skipped_pages: number
  ocr_pages: number
  total_pages: number
}

export async function localPdfOcr(file: File, onProgress?: (progress: { stage: string; current: number; total: number; message: string }) => void): Promise<LocalPdfOcrResult> {
  const electronAPI = (window as any).electronAPI;
  if (!electronAPI?.localPdfOcr) {
    throw new Error("本地 OCR 仅在桌面端可用");
  }
  // 将 File 写入临时文件，因为 Electron IPC 需要文件路径
  const buffer = await file.arrayBuffer();
  const tempPath = await electronAPI.saveTempFile(file.name, Array.from(new Uint8Array(buffer)));
  if (!tempPath) {
    throw new Error("无法创建临时文件");
  }
  // 监听进度事件
  let removeListener: (() => void) | undefined;
  if (onProgress && electronAPI.onOcrProgress) {
    removeListener = electronAPI.onOcrProgress(onProgress);
  }
  try {
    return await electronAPI.localPdfOcr(tempPath);
  } finally {
    removeListener?.();
    // 清理临时文件
    await electronAPI.deleteTempFile(tempPath).catch(() => {});
  }
}

// ===== Generate Content =====

export async function generateMindmap(fileNames: string[], prompt = ""): Promise<GenerateResponse> {
  return apiFetch("/api/generate", {
    method: "POST",
    body: JSON.stringify({ file_names: fileNames, user_prompt: prompt, output_type: "mindmap" }),
  });
}

export async function generateNotes(fileNames: string[], prompt = ""): Promise<GenerateResponse> {
  return apiFetch("/api/generate", {
    method: "POST",
    body: JSON.stringify({ file_names: fileNames, user_prompt: prompt, output_type: "notes" }),
  });
}

// ===== Saved Mindmaps =====

export async function saveMindmap(data: {
  title: string;
  output_type: string;
  content: string;
  mermaid_code?: string;
  file_names?: string[];
}): Promise<{ status: string; id: number }> {
  return apiFetch("/api/mindmaps", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listMindmaps(type?: string): Promise<SavedMindmap[]> {
  const query = type ? `?type=${type}` : "";
  const res = await apiFetch<{ items: SavedMindmap[] }>(`/api/mindmaps${query}`);
  return res.items || [];
}

export async function getMindmap(id: number): Promise<SavedMindmap> {
  return apiFetch(`/api/mindmaps/${id}`);
}

export async function deleteMindmap(id: number): Promise<{ status: string }> {
  return apiFetch(`/api/mindmaps/${id}`, { method: "DELETE" });
}

// ===== Quiz =====

export async function generateQuiz(
  fileNames: string[],
  numQuestions = 5,
  difficulty = "medium",
  qtypes = ["choice", "fill", "short_answer"]
): Promise<{ status: string; questions: QuizQuestion[] }> {
  return apiFetch("/api/quiz", {
    method: "POST",
    body: JSON.stringify({ file_names: fileNames, num_questions: numQuestions, difficulty, qtypes }),
  });
}

export async function checkQuizAnswer(question: QuizQuestion, userAnswer: string): Promise<{ correct: boolean; explanation: string }> {
  return apiFetch("/api/quiz/check", {
    method: "POST",
    body: JSON.stringify({ question, user_answer: userAnswer }),
  });
}

// ===== Flashcards =====

export async function generateFlashcards(
  fileNames: string[],
  numCards = 10,
  topicFocus = ""
): Promise<{ status: string; flashcards: Flashcard[] }> {
  return apiFetch("/api/flashcards", {
    method: "POST",
    body: JSON.stringify({ file_names: fileNames, num_cards: numCards, topic_focus: topicFocus }),
  });
}

// ===== Saved Quizzes =====

export async function saveQuiz(data: {
  title: string;
  questions: QuizQuestion[];
  score_correct?: number;
  score_total?: number;
  difficulty?: string;
  file_names?: string[];
}): Promise<{ status: string; id: number }> {
  return apiFetch("/api/quizzes", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listQuizzes(): Promise<SavedQuiz[]> {
  const res = await apiFetch<{ items: SavedQuiz[] }>("/api/quizzes");
  return res.items || [];
}

export async function getQuiz(id: number): Promise<SavedQuiz> {
  return apiFetch(`/api/quizzes/${id}`);
}

export async function deleteQuiz(id: number): Promise<{ status: string }> {
  return apiFetch(`/api/quizzes/${id}`, { method: "DELETE" });
}

// ===== Saved Flashcards =====

export async function saveFlashcardSet(data: {
  title: string;
  cards: Flashcard[];
  file_names?: string[];
}): Promise<{ status: string; id: number }> {
  return apiFetch("/api/flashcards/save", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listFlashcardSets(): Promise<SavedFlashcardSet[]> {
  const res = await apiFetch<{ items: SavedFlashcardSet[] }>("/api/flashcards/saved");
  return res.items || [];
}

export async function getFlashcardSet(id: number): Promise<SavedFlashcardSet> {
  return apiFetch(`/api/flashcards/saved/${id}`);
}

export async function deleteFlashcardSet(id: number): Promise<{ status: string }> {
  return apiFetch(`/api/flashcards/saved/${id}`, { method: "DELETE" });
}

// ===== Compare =====

export async function compareDocuments(fileNames: string[], focus = ""): Promise<{ status: string } & CompareResult> {
  return apiFetch("/api/compare", {
    method: "POST",
    body: JSON.stringify({ file_names: fileNames, focus }),
  });
}

// ===== Reading Progress =====

export async function updateReadingProgress(fileName: string, currentPage: number, totalPages = 0): Promise<{ status: string }> {
  return apiFetch("/api/reading-progress", {
    method: "POST",
    body: JSON.stringify({ file_name: fileName, current_page: currentPage, total_pages: totalPages }),
  });
}

export async function getAllReadingProgress(): Promise<{ progress: ReadingProgress[] }> {
  return apiFetch("/api/reading-progress");
}

// ===== Bookmarks =====

export async function addBookmark(fileName: string, pageNumber: number, title?: string, note?: string): Promise<{ id: number }> {
  return apiFetch("/api/bookmarks", {
    method: "POST",
    body: JSON.stringify({ file_name: fileName, page_number: pageNumber, title, note }),
  });
}

export async function getBookmarks(fileName?: string): Promise<{ bookmarks: Bookmark[] }> {
  const query = fileName ? `?file_name=${encodeURIComponent(fileName)}` : "";
  return apiFetch(`/api/bookmarks${query}`);
}

export async function deleteBookmark(bookmarkId: number): Promise<{ status: string }> {
  return apiFetch(`/api/bookmarks/${bookmarkId}`, { method: "DELETE" });
}

// ===== Tags =====

export async function createTag(name: string, color = "#5ac8fa"): Promise<{ id: number }> {
  return apiFetch("/api/tags", {
    method: "POST",
    body: JSON.stringify({ name, color }),
  });
}

export async function getTags(): Promise<{ tags: Tag[] }> {
  return apiFetch("/api/tags");
}

export async function deleteTag(tagId: number): Promise<{ status: string }> {
  return apiFetch(`/api/tags/${tagId}`, { method: "DELETE" });
}

// ===== Favorites =====

export async function getFavorites(sid: string): Promise<{ favorites: Favorite[] }> {
  return apiFetch(`/api/sessions/${sid}/favorites`);
}

export async function addFavorite(sid: string, content: string, question?: string): Promise<{ id: number }> {
  return apiFetch(`/api/sessions/${sid}/favorites`, {
    method: "POST",
    body: JSON.stringify({ content, question }),
  });
}

export async function removeFavorite(fid: number): Promise<{ status: string }> {
  return apiFetch(`/api/favorites/${fid}`, { method: "DELETE" });
}

// ===== Notes =====

export async function getSessionNotes(sid: string): Promise<{ notes: string }> {
  return apiFetch(`/api/sessions/${sid}/notes`);
}

export async function updateSessionNotes(sid: string, notes: string): Promise<{ status: string }> {
  return apiFetch(`/api/sessions/${sid}/notes`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
  });
}

// ===== Export =====

export function getExportUrl(sid: string, format: "md" | "html" = "md"): string {
  return `${API_BASE}/api/sessions/${sid}/export?format=${format}`;
}

// ===== Learning Progress =====

export async function getLearningProgress(sid: string): Promise<LearningProgress> {
  return apiFetch(`/api/sessions/${sid}/progress`);
}

export async function getWeakTopics(sid: string): Promise<{ weak_topics: { topic: string; question_count: number }[] }> {
  return apiFetch(`/api/sessions/${sid}/diagnosis`);
}

export async function getSessionTopics(sid: string): Promise<{ topics: string[] }> {
  return apiFetch(`/api/sessions/${sid}/topics`);
}

// ===== Diagnostics =====

export async function getDiagnostics(): Promise<{ startup_checks: Record<string, boolean>; vector_db_stats: VectorDbStats }> {
  return apiFetch("/api/diagnostics");
}

// ===== Settings =====

export async function getLlmSettings(): Promise<LlmSettings> {
  return apiFetch("/api/settings/llm");
}

export async function updateLlmSettings(data: {
  provider: "local" | "cloud" | "balance";
  cloud_base_url?: string;
  cloud_api_key?: string;
  cloud_model?: string;
  balance_api_key?: string;
  balance_base_url?: string;
  balance_model?: string;
}): Promise<{ status: string; provider: string }> {
  return apiFetch("/api/settings/llm", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ===== User Balance =====

export async function getBalance(): Promise<{ balance: number }> {
  return apiFetch("/api/user/balance");
}

export async function getUserUsageLogs(page = 1, size = 20): Promise<UsageLogsResponse> {
  return apiFetch(`/api/user/usage-logs?page=${page}&size=${size}`);
}

// ===== Admin =====

export async function getUsers(): Promise<{ users: UserInfo[] }> {
  return apiFetch("/api/admin/users");
}

export async function addBalance(uid: number, amount: number): Promise<{ user_id: number; balance: number }> {
  return apiFetch(`/api/admin/users/${uid}/balance`, {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
}

export async function getAdminUsageLogs(uid?: number, page = 1, size = 20): Promise<UsageLogsResponse> {
  const params = new URLSearchParams({ page: String(page), size: String(size) });
  if (uid) params.set("uid", String(uid));
  return apiFetch(`/api/admin/usage-logs?${params}`);
}

export async function banUser(uid: number, banned: boolean): Promise<{ user_id: number; banned: boolean }> {
  return apiFetch(`/api/admin/users/${uid}/ban`, {
    method: "POST",
    body: JSON.stringify({ banned }),
  });
}

export async function getRegistrationSetting(): Promise<{ allow_registration: boolean }> {
  return apiFetch("/api/admin/settings/registration");
}

export async function updateRegistrationSetting(allow: boolean): Promise<{ allow_registration: boolean }> {
  return apiFetch("/api/admin/settings/registration", {
    method: "PUT",
    body: JSON.stringify({ allow_registration: allow }),
  });
}

export async function checkRegistrationOpen(): Promise<{ allow_registration: boolean }> {
  const res = await fetch(`${API_BASE}/api/settings/registration`);
  if (!res.ok) throw new Error("Failed to check registration");
  return res.json();
}

// ===== PaddleOCR Setting =====

export async function getPaddleOcrSetting(): Promise<{ enabled: boolean; web_enabled: boolean; app_enabled: boolean }> {
  return apiFetch("/api/admin/settings/paddle-ocr");
}

export async function updatePaddleOcrSetting(data: { web_enabled?: boolean; app_enabled?: boolean }): Promise<{ web_enabled: boolean; app_enabled: boolean }> {
  return apiFetch("/api/admin/settings/paddle-ocr", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function checkPaddleOcrEnabled(clientType = "app"): Promise<{ enabled: boolean }> {
  const res = await fetch(`${API_BASE}/api/settings/paddle-ocr?client_type=${clientType}`);
  if (!res.ok) throw new Error("Failed to check paddle ocr setting");
  return res.json();
}

export async function getPaddleOcrGpuStatus(): Promise<{ gpu_available: boolean; device: string; details?: string }> {
  return apiFetch("/api/settings/paddle-ocr/gpu");
}

// ===== Site Messages =====

export async function sendMessage(toUserId: number, content: string): Promise<{ id: number; status: string }> {
  return apiFetch("/api/messages", {
    method: "POST",
    body: JSON.stringify({ to_user_id: toUserId, content }),
  });
}

export async function getMessages(type: "inbox" | "sent", page = 1, size = 20): Promise<{ items: SiteMessage[]; total: number; page: number; size: number }> {
  return apiFetch(`/api/messages/${type}?page=${page}&size=${size}`);
}

export async function getUnreadCount(): Promise<{ count: number }> {
  return apiFetch("/api/messages/unread-count");
}

export async function markMessageRead(id: number): Promise<{ status: string }> {
  return apiFetch(`/api/messages/${id}/read`, { method: "PUT" });
}

export async function markAllRead(): Promise<{ marked: number }> {
  return apiFetch("/api/messages/read-all", { method: "PUT" });
}

export async function broadcastMessage(content: string): Promise<{ status: string; count: number }> {
  return apiFetch("/api/messages/broadcast", {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

// ===== Download Files =====

export async function getDownloadFiles(): Promise<{ files: DownloadFile[] }> {
  return apiFetch("/api/downloads");
}

export async function uploadDownloadFile(file: File): Promise<{ id: number; status: string }> {
  const token = getToken();
  const formData = new FormData();
  formData.append("file", file);
  const headers: Record<string, string> = { "X-Client-Type": "desktop" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/downloads`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteDownloadFile(id: number): Promise<{ status: string }> {
  return apiFetch(`/api/downloads/${id}`, { method: "DELETE" });
}

export function getDownloadFileUrl(id: number): string {
  return `${API_BASE}/api/downloads/${id}/file`;
}
