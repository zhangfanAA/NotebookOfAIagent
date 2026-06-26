"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
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
import { Login } from "./Login";

// 背景主题（dark=true 表示深色背景，需要浅色文字）
const BG_THEMES = [
  { id: "default", label: "默认", className: "bg-theme-default", dark: false },
  { id: "aurora", label: "极光", className: "bg-theme-aurora", dark: true },
  { id: "ocean", label: "海洋", className: "bg-theme-ocean", dark: true },
  { id: "sunset", label: "日落", className: "bg-theme-sunset", dark: false },
  { id: "forest", label: "森林", className: "bg-theme-forest", dark: true },
  { id: "midnight", label: "午夜", className: "bg-theme-midnight", dark: true },
];

// Particle configuration for background
const PARTICLES = Array.from({ length: 20 }, (_, i) => ({
  id: i,
  left: `${Math.random() * 100}%`,
  delay: Math.random() * 10,
  duration: 8 + Math.random() * 10,
  size: 1 + Math.random() * 2,
  opacity: 0.15 + Math.random() * 0.3,
}));

export default function Home() {
  const [page, setPage] = useState<"login" | "app">(
    isAuthenticated() ? "app" : "login"
  );
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("dark_mode") === "true";
  });

  // 背景状态
  const [bgTheme, setBgTheme] = useState(() => {
    if (typeof window === "undefined") return "default";
    return localStorage.getItem("bg_theme") || "default";
  });
  const [bgImage, setBgImage] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("bg_image") || "";
  });

  // 监听认证状态变化（401 时触发）
  useEffect(() => {
    const onAuthChange = () => {
      if (!isAuthenticated()) {
        setPage("login");
      }
    };
    window.addEventListener("auth-change", onAuthChange);
    return () => window.removeEventListener("auth-change", onAuthChange);
  }, []);

  if (page === "login") {
    return <Login onLoginSuccess={() => setPage("app")} />;
  }

  return (
    <MainApp
      darkMode={darkMode}
      setDarkMode={setDarkMode}
      bgTheme={bgTheme}
      setBgTheme={setBgTheme}
      bgImage={bgImage}
      setBgImage={setBgImage}
      onLogout={() => setPage("login")}
    />
  );
}

function MainApp({
  darkMode,
  setDarkMode,
  bgTheme,
  setBgTheme,
  bgImage,
  setBgImage,
  onLogout,
}: {
  darkMode: boolean;
  setDarkMode: (v: boolean) => void;
  bgTheme: string;
  setBgTheme: (v: string) => void;
  bgImage: string;
  setBgImage: (v: string) => void;
  onLogout: () => void;
}) {
  const [activePanel, setActivePanel] = useState<PanelType>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [panelWidth, setPanelWidth] = useState(40);
  const isResizingRef = useRef(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
    localStorage.setItem("dark_mode", String(darkMode));
  }, [darkMode]);

  // 未读消息轮询
  const fetchUnread = useCallback(async () => {
    try {
      const res = await api.getUnreadCount();
      setUnreadCount(res.count);
    } catch {}
  }, []);

  useEffect(() => {
    fetchUnread();
    const timer = setInterval(fetchUnread, 30000);
    return () => clearInterval(timer);
  }, [fetchUnread]);

  useEffect(() => {
    if (!sessionId && sessions.length > 0) {
      setSessionId(sessions[0].session_id);
    }
  }, [sessions, sessionId]);

  useEffect(() => {
    if (pendingQuestion && !sessionId) {
      api.createSession().then((res) => {
        setSessionId(res.session_id);
        setSessions((prev) => [{ session_id: res.session_id, title: res.title, created_at: new Date().toISOString(), messages_count: 0 }, ...prev]);
      }).catch(() => setPendingQuestion(null));
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
      setPanelWidth(Math.min(70, Math.max(25, startWidth + (dx / containerWidth) * 100)));
    };
    const onMouseUp = () => {
      isResizingRef.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, [panelWidth]);

  // 背景切换
  const handleBgChange = useCallback((themeId: string) => {
    setBgTheme(themeId);
    setBgImage("");
    localStorage.setItem("bg_theme", themeId);
    localStorage.removeItem("bg_image");
  }, [setBgTheme, setBgImage]);

  const handleBgImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const url = ev.target?.result as string;
      setBgImage(url);
      setBgTheme("default");
      localStorage.setItem("bg_image", url);
      localStorage.setItem("bg_theme", "default");
    };
    reader.readAsDataURL(file);
  }, [setBgImage, setBgTheme]);

  const isFullPage = activePanel === "stats" || activePanel === "compare" || activePanel === "download" || activePanel === "settings" || activePanel === "admin" || activePanel === "messages";
  const isRightPanel = activePanel === "mindmap" || activePanel === "quiz" || activePanel === "flashcard";

  // 背景样式与字体颜色
  const currentTheme = BG_THEMES.find(t => t.id === bgTheme);
  const bgClass = bgImage ? "" : (currentTheme?.className || "bg-theme-default");
  const bgStyle = bgImage ? { backgroundImage: `url(${bgImage})` } : {};
  const isDarkBg = bgImage ? true : (currentTheme?.dark ?? false);

  // 首次切换背景主题时，自动设置深色模式（用户可手动覆盖）
  const prevThemeRef = useRef(bgTheme);
  useEffect(() => {
    if (prevThemeRef.current !== bgTheme) {
      prevThemeRef.current = bgTheme;
      if (bgTheme !== "default") {
        setDarkMode(isDarkBg);
      }
    }
  }, [bgTheme, isDarkBg, setDarkMode]);

  return (
    <div
      className={`relative flex h-screen overflow-hidden app-bg ${bgClass}`}
      style={bgStyle}
    >
      {/* CSS Particles background */}
      <div className="particles">
        {PARTICLES.map((p) => (
          <span
            key={p.id}
            style={{
              left: p.left,
              bottom: "-10px",
              width: `${p.size}px`,
              height: `${p.size}px`,
              opacity: p.opacity,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.duration}s`,
            }}
          />
        ))}
      </div>

      {/* Mobile sidebar overlay */}
      <AnimatePresence>
        {isMobileSidebarOpen && (
          <motion.div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setIsMobileSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        className={`
          fixed inset-y-0 left-0 z-50 w-72 flex-shrink-0
          transform transition-transform duration-300 ease-out
          lg:relative lg:translate-x-0
          ${isMobileSidebarOpen ? "translate-x-0" : "-translate-x-full"}
        `}
        initial={{ x: -20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="h-full glass-subtle shadow-glass">
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
        </div>
      </motion.aside>

      {/* Gradient divider between sidebar and content */}
      <div className="hidden lg:block absolute left-72 top-0 bottom-0 w-px z-30"
        style={{ background: "linear-gradient(to bottom, transparent, rgba(99,102,241,0.15), rgba(139,92,246,0.1), transparent)" }}
      />

      {/* Main content */}
      <motion.main
        className="flex flex-1 overflow-hidden"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.4 }}
      >
        <AnimatePresence mode="wait">
          {isFullPage ? (
            <motion.div
              key="fullpage"
              className="flex-1 overflow-y-auto p-2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="glass-card rounded-2xl min-h-full">
                {activePanel === "stats" && <StatsPanel sessionId={sessionId} />}
                {activePanel === "compare" && <ComparePanel />}
                {activePanel === "download" && <DownloadPanel />}
                {activePanel === "settings" && (
                  <SettingsPanel
                    bgTheme={bgTheme}
                    bgImage={bgImage}
                    onBgChange={handleBgChange}
                    onBgImageUpload={handleBgImageUpload}
                    bgThemes={BG_THEMES}
                  />
                )}
                {activePanel === "admin" && <AdminPanel />}
                {activePanel === "messages" && <MessagePanel userRole={getRole() || 1} onUnreadChange={fetchUnread} />}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="chat-layout"
              className="flex flex-1 overflow-hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              {/* Chat area */}
              <div className="flex-1 flex flex-col overflow-hidden min-w-0">
                {/* Mobile header */}
                <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2 lg:hidden glass">
                  <button
                    onClick={() => setIsMobileSidebarOpen(true)}
                    className="rounded-lg p-2 hover:bg-white/[0.06] transition-colors"
                  >
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                  </button>
                  <span className="font-semibold text-sm">智能学习助手</span>
                </div>
                <motion.div
                  className="flex-1 flex flex-col overflow-hidden m-2 rounded-2xl glass-card"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1, duration: 0.4 }}
                >
                  <ChatArea
                    sessionId={sessionId}
                    messages={messages}
                    setMessages={setMessages}
                    onMobileMenuOpen={() => setIsMobileSidebarOpen(true)}
                    pendingQuestion={pendingQuestion}
                    onPendingQuestionConsumed={() => setPendingQuestion(null)}
                    onTitleUpdate={(title) => {
                      setSessions((prev) =>
                        prev.map((s) =>
                          s.session_id === sessionId ? { ...s, title } : s
                        )
                      );
                    }}
                  />
                </motion.div>
              </div>

              {/* Right panel — resizable */}
              <AnimatePresence>
                {isRightPanel && (
                  <motion.div
                    key={activePanel}
                    className="hidden lg:flex lg:flex-col lg:overflow-hidden relative m-2 ml-0 rounded-2xl glass-card"
                    style={{ width: `${panelWidth}%`, minWidth: "25%", maxWidth: "70%" }}
                    initial={{ opacity: 0, x: 40, scale: 0.97 }}
                    animate={{ opacity: 1, x: 0, scale: 1 }}
                    exit={{ opacity: 0, x: 40, scale: 0.97 }}
                    transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                  >
                    <div
                      className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize z-10 hover:bg-[#6366f1]/20 transition-colors rounded-l-2xl"
                      onMouseDown={handleResizeStart}
                    />
                    {activePanel === "mindmap" && <MindmapPanel sessionId={sessionId} onNodeClick={(label) => setPendingQuestion(`请详细解释"${label}"这个知识点`)} />}
                    {activePanel === "quiz" && <QuizPanel />}
                    {activePanel === "flashcard" && <FlashcardPanel />}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.main>
    </div>
  );
}
