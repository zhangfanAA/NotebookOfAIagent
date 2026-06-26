"use client";

import { useRef, useEffect, useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageBubble } from "@/components/message-bubble";
import { InputBar } from "@/components/input-bar";
import { AgentSidebar } from "@/components/agent-sidebar";
import { MemoryPanel } from "@/components/memory-panel";
import { ChevronDown, BookOpen, Sparkles } from "lucide-react";
import type { Message, Source, AgentStep } from "@/lib/types";
import * as api from "@/lib/api";

interface ChatAreaProps {
  sessionId: string | null;
  messages: Message[];
  setMessages: (msgs: Message[] | ((prev: Message[]) => Message[])) => void;
  onMobileMenuOpen: () => void;
  pendingQuestion?: string | null;
  onPendingQuestionConsumed?: () => void;
  onTitleUpdate?: (title: string) => void;
}

export function ChatArea({ sessionId, messages, setMessages, onMobileMenuOpen, pendingQuestion, onPendingQuestionConsumed, onTitleUpdate }: ChatAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [agentVisualization, setAgentVisualization] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("agent_mode") === "true";
  });

  const setMessagesRef = useRef(setMessages);
  useEffect(() => { setMessagesRef.current = setMessages; }, [setMessages]);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  // Track scroll position for scroll-to-bottom button
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handleScroll = () => {
      const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      setShowScrollBtn(distFromBottom > 120);
    };
    el.addEventListener("scroll", handleScroll);
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  // 监听 agent_mode 变化
  useEffect(() => {
    const handler = () => setAgentVisualization(localStorage.getItem("agent_mode") === "true");
    window.addEventListener("storage", handler);
    window.addEventListener("agent-mode-changed", handler);
    return () => {
      window.removeEventListener("storage", handler);
      window.removeEventListener("agent-mode-changed", handler);
    };
  }, []);

  /** 将最后一条助手消息标记为完成 */
  const finalizeLastMessage = useCallback((sm: typeof setMessages, extra?: Partial<Message>) => {
    sm((prev) => {
      const updated = [...prev];
      const lastIdx = updated.length - 1;
      if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
        const last = updated[lastIdx];
        const content = last.content === "思考中..." ? (extra?.content || "（无响应）") : last.content;
        updated[lastIdx] = { ...last, ...extra, content, isStreaming: false };
      }
      return updated;
    });
    setAgentSteps([]);
  }, []);

  /** 核心发送函数 */
  const handleSend = useCallback((question: string, memoryMode: boolean = false, agentMode: boolean = false) => {
    if (!sessionId || !question.trim()) return;
    if (abortRef.current) return;

    const sm = setMessagesRef.current;

    // 1. 添加用户消息
    sm((prev) => [...prev, { role: "user", content: question }]);

    // 2. 添加助手占位消息
    sm((prev) => [...prev, { role: "assistant", content: "思考中...", isStreaming: true, agentSteps: agentMode ? [] : undefined }]);

    setIsStreaming(true);
    setAgentSteps([]);

    if (agentMode) {
      // ===== Agent 模式 =====
      const steps: AgentStep[] = [];

      const abort = api.agentStream(
        question,
        sessionId || "",
        (chunk) => {
          if (chunk.type === "tool_call" && chunk.tool) {
            const step: AgentStep = { type: "tool_call", tool: chunk.tool, args: chunk.args, id: chunk.id, timestamp: Date.now() };
            steps.push(step);
            setAgentSteps([...steps]);
            sm((prev) => {
              const updated = [...prev];
              const lastIdx = updated.length - 1;
              if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
                updated[lastIdx] = { ...updated[lastIdx], agentSteps: [...steps], isStreaming: true };
              }
              return updated;
            });
          } else if (chunk.type === "tool_result" && chunk.tool) {
            const step: AgentStep = { type: "tool_result", tool: chunk.tool, content: chunk.content, id: chunk.id, timestamp: Date.now() };
            steps.push(step);
            setAgentSteps([...steps]);
            sm((prev) => {
              const updated = [...prev];
              const lastIdx = updated.length - 1;
              if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
                updated[lastIdx] = { ...updated[lastIdx], agentSteps: [...steps], isStreaming: true };
              }
              return updated;
            });
          } else if (chunk.type === "token") {
            const token = chunk.content || (typeof chunk.data === "string" ? chunk.data : "") || "";
            if (!token) return;
            sm((prev) => {
              const updated = [...prev];
              const lastIdx = updated.length - 1;
              const last = updated[lastIdx];
              if (lastIdx < 0 || last.role !== "assistant") return prev;
              const newContent = last.content === "思考中..." ? token : last.content + token;
              updated[lastIdx] = { ...last, content: newContent, isStreaming: true };
              return updated;
            });
          } else if (chunk.type === "result") {
            const resultData = chunk.data as { sources?: Source[]; confidence?: number } | undefined;
            if (resultData) {
              sm((prev) => {
                const updated = [...prev];
                const lastIdx = updated.length - 1;
                if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
                  updated[lastIdx] = {
                    ...updated[lastIdx],
                    sources: resultData.sources || updated[lastIdx].sources,
                    confidence: resultData.confidence ?? updated[lastIdx].confidence,
                  };
                }
                return updated;
              });
            }
          } else if (chunk.type === "title") {
            // 标题更新事件
            const newTitle = chunk.data as string;
            if (newTitle && onTitleUpdate) {
              onTitleUpdate(newTitle);
            }
          }
        },
        (err) => {
          finalizeLastMessage(sm, { content: `⚠️ Agent 连接失败: ${err.message}` });
          abortRef.current = null;
          setIsStreaming(false);
        },
        () => {
          finalizeLastMessage(sm);
          abortRef.current = null;
          setIsStreaming(false);
        },
        memoryMode
      );

      abortRef.current = abort;
    } else {
      // ===== 普通模式 =====
      const abort = api.chatStream(
        question,
        sessionId,
        (chunk) => {
          if (chunk.type === "token") {
            const token = typeof chunk.data === "string" ? chunk.data : chunk.content || "";
            if (!token) return;
            sm((prev) => {
              const updated = [...prev];
              const lastIdx = updated.length - 1;
              const last = updated[lastIdx];
              if (lastIdx < 0 || last.role !== "assistant") return prev;
              const newContent = last.content === "思考中..." ? token : last.content + token;
              updated[lastIdx] = { ...last, content: newContent, isStreaming: true };
              return updated;
            });
          } else if (chunk.type === "result") {
            const resultData = chunk.data as { sources?: Source[]; confidence?: number } | undefined;
            if (resultData) {
              sm((prev) => {
                const updated = [...prev];
                const lastIdx = updated.length - 1;
                if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
                  updated[lastIdx] = { ...updated[lastIdx], sources: resultData.sources || updated[lastIdx].sources, confidence: resultData.confidence ?? updated[lastIdx].confidence };
                }
                return updated;
              });
            }
          } else if (chunk.type === "title") {
            // 标题更新事件
            const newTitle = chunk.data as string;
            if (newTitle && onTitleUpdate) {
              onTitleUpdate(newTitle);
            }
          } else if (chunk.type === "error") {
            const errorMsg = typeof chunk.data === "string" ? chunk.data : chunk.content || "出错了";
            finalizeLastMessage(sm, { content: `⚠️ ${errorMsg}` });
          }
        },
        (err) => {
          const msg = err.message || "";
          if (msg.includes("余额不足") || msg.includes("402")) {
            sm((prev) => prev.filter((_, i) => i < prev.length - 1 || prev[i].role !== "assistant" || prev[i].content !== "思考中..."));
            alert("余额不足，请联系管理员充值后再试");
          } else {
            finalizeLastMessage(sm, { content: `⚠️ 连接失败: ${msg}` });
          }
          abortRef.current = null;
          setIsStreaming(false);
        },
        () => {
          finalizeLastMessage(sm);
          abortRef.current = null;
          setIsStreaming(false);
        },
        memoryMode
      );

      abortRef.current = abort;
    }
  }, [sessionId, finalizeLastMessage]);

  // 处理 pending 问题（思维导图双击等场景，始终走普通聊天模式）
  useEffect(() => {
    if (pendingQuestion && sessionId && !abortRef.current) {
      const memoryMode = typeof window !== "undefined" && localStorage.getItem("memory_mode") === "true";
      handleSend(pendingQuestion, memoryMode, false);
      onPendingQuestionConsumed?.();
    }
  }, [pendingQuestion, sessionId, handleSend, onPendingQuestionConsumed]);

  const handleStop = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    finalizeLastMessage(setMessagesRef.current);
    setIsStreaming(false);
  }, [finalizeLastMessage]);

  // 从最后一条助手消息获取 agentSteps
  const lastAssistantSteps: AgentStep[] = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const steps = messages[i].agentSteps;
      if (messages[i].role === "assistant" && steps && steps.length > 0) {
        return steps;
      }
    }
    return [] as AgentStep[];
  })();

  const sidebarSteps = agentSteps.length > 0 ? agentSteps : lastAssistantSteps;
  const showSidebar = agentVisualization;

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="flex flex-1 flex-col overflow-hidden">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 relative">
          <AnimatePresence mode="wait">
            {messages.length === 0 ? (
              /* Empty state with animated illustration */
              <motion.div
                key="empty"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.5, ease: "easeOut" as const }}
                className="flex h-full flex-col items-center justify-center"
              >
                <motion.div
                  className="relative mb-6"
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" as const }}
                >
                  <div className="h-24 w-24 rounded-3xl glass-card flex items-center justify-center">
                    <BookOpen className="h-10 w-10 text-indigo-400" />
                  </div>
                  <motion.div
                    className="absolute -bottom-1 -right-1 h-8 w-8 rounded-full glass-card flex items-center justify-center"
                    animate={{ rotate: [0, 15, -15, 0] }}
                    transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" as const }}
                  >
                    <Sparkles className="h-4 w-4 text-purple-400" />
                  </motion.div>
                </motion.div>
                <h2 className="text-xl font-semibold mb-2 text-glow bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
                  智能学习助手
                </h2>
                <p className="text-sm text-[#94a3b8]">上传文件，开始你的学习之旅</p>
              </motion.div>
            ) : (
              /* Message list with staggered entry */
              <motion.div
                key="messages"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mx-auto max-w-3xl space-y-4"
              >
                {messages.map((msg, i) => (
                  <motion.div
                    key={`${sessionId}-${i}`}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.35,
                      delay: i === messages.length - 1 ? 0.05 : 0,
                      ease: "easeOut" as const,
                    }}
                  >
                    <MessageBubble message={msg} />
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Scroll-to-bottom button */}
          <AnimatePresence>
            {showScrollBtn && (
              <motion.button
                initial={{ opacity: 0, y: 10, scale: 0.8 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.8 }}
                transition={{ type: "spring", stiffness: 400, damping: 25 }}
                onClick={scrollToBottom}
                className="fixed bottom-28 right-8 z-20 h-9 w-9 rounded-full glass-card flex items-center justify-center text-[#94a3b8] hover:text-indigo-400 transition-colors glow-border"
              >
                <ChevronDown className="h-4 w-4" />
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        <MemoryPanel sessionId={sessionId} visible={!!sessionId} />

        <InputBar
          onSend={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
          disabled={!sessionId}
        />
      </div>

      {showSidebar && (
        <AgentSidebar
          steps={sidebarSteps}
          isStreaming={isStreaming && agentSteps.length > 0}
          visible={showSidebar}
        />
      )}
    </div>
  );
}
