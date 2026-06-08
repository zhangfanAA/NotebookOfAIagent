"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { ChatArea } from "@/components/chat-area";
import { MindmapPanel } from "@/components/mindmap-panel";
import { QuizPanel } from "@/components/quiz-panel";
import { FlashcardPanel } from "@/components/flashcard-panel";
import { StatsPanel } from "@/components/stats-panel";
import { ComparePanel } from "@/components/compare-panel";
import { DownloadPanel } from "@/components/download-panel";
import { SettingsPanel } from "@/components/settings-panel";
import { AdminPanel } from "@/components/admin-panel";
import { MessagePanel } from "@/components/message-panel";
import type { PanelType, Session, Message } from "@/lib/types";
import * as api from "@/lib/api";
import { isAuthenticated, getRole } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [darkMode, setDarkMode] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
    } else {
      setAuthChecked(true);
    }
  }, [router]);
  const [activePanel, setActivePanel] = useState<PanelType>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);

  // 右侧面板可调整宽度
  const [panelWidth, setPanelWidth] = useState(40); // 百分比
  const isResizingRef = useRef(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);

  // 未读消息轮询
  const fetchUnread = useCallback(async () => {
    try {
      const res = await api.getUnreadCount();
      setUnreadCount(res.count);
    } catch {
      // silent
    }
  }, []);
  useEffect(() => {
    fetchUnread();
    const timer = setInterval(fetchUnread, 30000);
    return () => clearInterval(timer);
  }, [fetchUnread]);

  // 自动选中最近的会话（首次加载时）
  useEffect(() => {
    if (!sessionId && sessions.length > 0) {
      setSessionId(sessions[0].session_id);
    }
  }, [sessions, sessionId]);

  // 当有待处理问题但没有会话时，自动创建会话
  useEffect(() => {
    if (pendingQuestion && !sessionId) {
      api.createSession().then((res) => {
        setSessionId(res.session_id);
        setSessions((prev) => [{ session_id: res.session_id, title: res.title, created_at: new Date().toISOString(), messages_count: 0 }, ...prev]);
      }).catch(() => {
        setPendingQuestion(null);
      });
    }
  }, [pendingQuestion, sessionId]);

  const togglePanel = useCallback((panel: PanelType) => {
    setActivePanel((prev) => (prev === panel ? null : panel));
  }, []);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizingRef.current = true;
    const startX = e.clientX;
    const startWidth = panelWidth;
    const containerWidth = window.innerWidth;

    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizingRef.current) return;
      const dx = startX - ev.clientX;
      const newWidth = Math.min(70, Math.max(25, startWidth + (dx / containerWidth) * 100));
      setPanelWidth(newWidth);
    };
    const onMouseUp = () => {
      isResizingRef.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, [panelWidth]);

  const isFullPage = activePanel === "stats" || activePanel === "compare" || activePanel === "download" || activePanel === "settings" || activePanel === "admin" || activePanel === "messages";
  const isRightPanel = activePanel === "mindmap" || activePanel === "quiz" || activePanel === "flashcard";

  if (!authChecked) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile sidebar overlay */}
      {isMobileSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm lg:hidden"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 w-72 flex-shrink-0
          transform transition-transform duration-300 ease-out
          lg:relative lg:translate-x-0
          ${isMobileSidebarOpen ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        <Sidebar
          darkMode={darkMode}
          onToggleDark={() => setDarkMode((d) => !d)}
          activePanel={activePanel}
          onTogglePanel={togglePanel}
          sessionId={sessionId}
          onSelectSession={(sid) => {
            setSessionId(sid);
            setIsMobileSidebarOpen(false);
          }}
          sessions={sessions}
          setSessions={setSessions}
          setMessages={setMessages}
          unreadCount={unreadCount}
          onOpenMessages={() => setActivePanel("messages")}
        />
      </aside>

      {/* Main content */}
      <main className="flex flex-1 overflow-hidden">
        {isFullPage ? (
          <div className="flex-1 overflow-y-auto">
            {activePanel === "stats" && <StatsPanel sessionId={sessionId} />}
            {activePanel === "compare" && <ComparePanel />}
            {activePanel === "download" && <DownloadPanel />}
            {activePanel === "settings" && <SettingsPanel />}
            {activePanel === "admin" && <AdminPanel />}
            {activePanel === "messages" && <MessagePanel userRole={getRole() || 1} onUnreadChange={fetchUnread} />}
          </div>
        ) : (
          <>
            {/* Chat area */}
            <div className="flex-1 flex flex-col overflow-hidden min-w-0">
              {/* Mobile header */}
              <div className="flex items-center gap-2 border-b px-4 py-2 lg:hidden">
                <button
                  onClick={() => setIsMobileSidebarOpen(true)}
                  className="rounded-lg p-2 hover:bg-muted"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
                <span className="font-semibold">智能学习助手</span>
              </div>
              <ChatArea
                sessionId={sessionId}
                messages={messages}
                setMessages={setMessages}
                onMobileMenuOpen={() => setIsMobileSidebarOpen(true)}
                pendingQuestion={pendingQuestion}
                onPendingQuestionConsumed={() => setPendingQuestion(null)}
              />
            </div>

            {/* Right panel — resizable */}
            {isRightPanel && (
              <div
                className="hidden lg:flex lg:flex-col lg:overflow-hidden border-l relative"
                style={{ width: `${panelWidth}%`, minWidth: "25%", maxWidth: "70%" }}
              >
                {/* Resize handle */}
                <div
                  className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize z-10 hover:bg-primary/20 transition-colors"
                  onMouseDown={handleResizeStart}
                />
                {activePanel === "mindmap" && <MindmapPanel sessionId={sessionId} onNodeClick={(label) => setPendingQuestion(`请详细解释"${label}"这个知识点`)} />}
                {activePanel === "quiz" && <QuizPanel />}
                {activePanel === "flashcard" && <FlashcardPanel />}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
