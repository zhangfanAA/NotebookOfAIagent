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
  AgentChunk,
  GenerateResponse,
  SavedMindmap,
  SavedQuiz,
  SavedFlashcardSet,
  LlmSettings,
  UserInfo,
  UsageLogsResponse,
  SiteMessage,
  DownloadFile,
} from "./types";
import { getToken, removeToken } from "./auth";

const API_BASE = (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) || "http://localhost:8000";

// 检测是否在 Electron 桌面端环境中运行
function getClientType(): string {
  if (typeof window !== "undefined" && (window as any).electronAPI) {
    return "desktop";
  }
  return "web";
}

// ===== Generic fetch =====

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Client-Type": getClientType(),
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
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
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
    headers: { "Content-Type": "application/json" },
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
    headers: { "Content-Type": "application/json" },
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
  onDone: () => void,
  memoryMode: boolean = false
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const token = getToken();
      const headers: Record<string, string> = { "Content-Type": "application/json", "X-Client-Type": getClientType() };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({ question, session_id: sessionId, memory_mode: memoryMode }),
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

export function agentStream(
  question: string,
  sessionId: string,
  onChunk: (chunk: AgentChunk) => void,
  onError: (err: Error) => void,
  onDone: () => void,
  memoryMode: boolean = false
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const token = getToken();
      const headers: Record<string, string> = { "Content-Type": "application/json", "X-Client-Type": getClientType() };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_BASE}/api/agent/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({ question, session_id: sessionId, memory_mode: memoryMode }),
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
            const chunk: AgentChunk = JSON.parse(data);
            onChunk(chunk);
          } catch {
            // skip malformed JSON
          }
        }
      }
      onDone();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        const e = err as Error;
        // 给出更友好的错误信息
        if (e.message.includes("Failed to fetch") || e.message.includes("NetworkError") || e.message.includes("network error")) {
          onError(new Error("无法连接到 Agent 服务，请确认后端已启动且支持 Supervisor Agent"));
        } else {
          onError(e);
        }
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

export async function uploadDocument(file: File): Promise<{ status: string; message: string; ocr_skipped?: boolean; ocr_skipped_pages?: number }> {
  const token = getToken();
  const formData = new FormData();
  formData.append("file", file);
  const headers: Record<string, string> = { "X-Client-Type": getClientType() };
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

// ===== Memory =====

export interface MemoryStats {
  total_records: number;
  session_records: number;
  collection_name: string;
}

export interface MemoryRecord {
  question: string;
  answer: string;
  timestamp: number;
  sources: string;
  score?: number;
}

export async function getMemoryStats(sessionId?: string): Promise<MemoryStats> {
  const params = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return apiFetch(`/api/memory/stats${params}`);
}

export async function getMemoryRecent(sessionId: string): Promise<{ records: MemoryRecord[]; total: number }> {
  return apiFetch(`/api/memory/recent?session_id=${encodeURIComponent(sessionId)}`);
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

export async function checkPaddleOcrEnabled(clientType = "web"): Promise<{ enabled: boolean }> {
  const res = await fetch(`${API_BASE}/api/settings/paddle-ocr?client_type=${clientType}`);
  if (!res.ok) throw new Error("Failed to check paddle ocr setting");
  return res.json();
}

// ===== Cloud OCR (Web 端通过后端代理) =====

export async function cloudOcrWeb(file: File, token: string, onProgress?: (msg: string) => void): Promise<{ pages: any[]; total_pages: number; ocr_pages: number }> {
  onProgress?.("正在上传文件到云端 OCR...");
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/ocr/cloud`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function getCloudOcrToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("cloud_ocr_token") || "";
}

export function setCloudOcrToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("cloud_ocr_token", token);
}

export function extractBearerToken(input: string): string {
  const trimmed = input.trim();
  if (trimmed.toLowerCase().startsWith("bearer ")) {
    return trimmed.slice(7).trim();
  }
  return trimmed;
}

// ===== Balance OCR =====

export async function balanceOcr(file: File, onProgress?: (status: string) => void): Promise<{ pages: any[]; total_pages: number; ocr_pages: number; cost: number }> {
  const formData = new FormData();
  formData.append("file", file);
  const token = getToken();
  const headers: Record<string, string> = { "X-Client-Type": getClientType() };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // 1. 提交任务
  const res = await fetch(`${API_BASE}/api/ocr/balance`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const submitData = await res.json();
  const jobId = submitData.job_id;

  // 2. 轮询结果
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 5000));
    onProgress?.(`OCR 处理中... (${i * 5 + 5}s)`);

    const pollRes = await fetch(`${API_BASE}/api/ocr/balance/${jobId}`, {
      headers: { "X-Client-Type": getClientType(), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
    if (!pollRes.ok) continue;

    const pollData = await pollRes.json();
    if (pollData.status === "done") {
      return { pages: pollData.pages, total_pages: pollData.total_pages, ocr_pages: pollData.total_pages, cost: pollData.cost };
    } else if (pollData.status === "failed") {
      throw new Error(pollData.error || "OCR 处理失败");
    }
  }
  throw new Error("OCR 任务超时");
}

// ===== Admin Balance Config =====

export async function getBalanceOcrConfig(): Promise<{ api_key: string }> {
  return apiFetch("/api/admin/settings/balance-ocr");
}

export async function updateBalanceOcrConfig(api_key: string): Promise<{ status: string }> {
  return apiFetch("/api/admin/settings/balance-ocr", {
    method: "PUT",
    body: JSON.stringify({ api_key }),
  });
}

export async function getBalanceModelConfig(): Promise<{ api_key: string; base_url: string; model: string }> {
  return apiFetch("/api/admin/settings/balance-model");
}

export async function updateBalanceModelConfig(data: { balance_api_key?: string; balance_base_url?: string; balance_model?: string }): Promise<{ status: string }> {
  return apiFetch("/api/admin/settings/balance-model", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ===== Connection Test =====

export async function testOcrConnection(): Promise<{ ok: boolean; message: string }> {
  return apiFetch("/api/test/ocr-connection", { method: "POST" });
}

export async function testBalanceModelConnection(): Promise<{ ok: boolean; message: string }> {
  return apiFetch("/api/test/balance-model", { method: "POST" });
}

export async function testCloudConnection(data: { cloud_api_key?: string; cloud_base_url?: string; cloud_model?: string }): Promise<{ ok: boolean; message: string }> {
  return apiFetch("/api/test/cloud-connection", {
    method: "POST",
    body: JSON.stringify(data),
  });
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
  const headers: Record<string, string> = { "X-Client-Type": getClientType() };
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
