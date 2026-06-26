"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, CheckCircle, Loader2, Zap } from "lucide-react";
import type { AgentStep } from "@/lib/types";

// 工具名 → 中文名 + 图标 + 描述
const TOOL_META: Record<string, { label: string; icon: string; desc: string }> = {
  rag_query: { label: "知识检索", icon: "🔍", desc: "从文档中检索相关信息" },
  list_documents: { label: "列出文档", icon: "📚", desc: "查看已上传的学习资料" },
  upload_document: { label: "上传文档", icon: "📄", desc: "上传新的学习资料" },
  delete_document: { label: "删除文档", icon: "🗑️", desc: "删除指定文档" },
  generate_mindmap: { label: "生成思维导图", icon: "🗺️", desc: "基于文档生成思维导图" },
  generate_quiz: { label: "生成测验", icon: "📝", desc: "基于文档生成练习题" },
  check_quiz_answer: { label: "判分", icon: "✅", desc: "检查测验答案" },
  generate_flashcards: { label: "生成闪卡", icon: "🃏", desc: "基于文档生成闪卡" },
  compare_documents: { label: "对比文档", icon: "⚖️", desc: "对比分析文档异同" },
};

function getToolMeta(tool: string) {
  return TOOL_META[tool] || { label: tool, icon: "🔧", desc: "调用工具" };
}

function formatArgs(args?: Record<string, unknown>): string {
  if (!args || Object.keys(args).length === 0) return "";
  const parts: string[] = [];
  for (const [k, v] of Object.entries(args)) {
    if (k === "user_id" || k === "session_id") continue;
    if (v === undefined || v === null) continue;
    const val = typeof v === "string" ? v : Array.isArray(v) ? v.join(", ") : String(v);
    if (val.length > 60) {
      parts.push(`${k}="${val.slice(0, 60)}..."`);
    } else {
      parts.push(`${k}="${val}"`);
    }
  }
  return parts.join("，");
}

function formatResultSummary(tool: string, content?: unknown): { title: string; details: string[] } {
  if (!content) return { title: "执行完成", details: [] };
  const str = typeof content === "string" ? content : JSON.stringify(content);

  try {
    const data = JSON.parse(str);

    if (tool === "list_documents" && data.documents) {
      const docs = data.documents as Array<{ file_name: string; chunks_count: number; status: string }>;
      return {
        title: `找到 ${docs.length} 份文档`,
        details: docs.map(d => `${d.file_name}（${d.chunks_count} 个切片）`),
      };
    }

    if (tool === "rag_query" && data.answer) {
      const conf = data.confidence ? `，置信度 ${Math.round(data.confidence * 100)}%` : "";
      const srcCount = data.sources?.length ? `，引用 ${data.sources.length} 个来源` : "";
      return {
        title: `检索完成${conf}${srcCount}`,
        details: [String(data.answer).slice(0, 150) + (String(data.answer).length > 150 ? "..." : "")],
      };
    }

    if (tool === "generate_quiz" && (data.questions || data.quiz)) {
      const questions = data.questions || data.quiz || [];
      return {
        title: `生成 ${questions.length} 道题目`,
        details: questions.slice(0, 3).map((q: { question: string }) => q.question?.slice(0, 60)),
      };
    }

    if (tool === "generate_mindmap") {
      return {
        title: data.mindmap ? "思维导图生成完成" : "笔记生成完成",
        details: [],
      };
    }

    if (tool === "generate_flashcards" && data.cards) {
      return {
        title: `生成 ${data.cards.length} 张闪卡`,
        details: data.cards.slice(0, 2).map((c: { front: string }) => c.front?.slice(0, 60)),
      };
    }

    if (tool === "compare_documents") {
      return {
        title: "文档对比完成",
        details: data.summary ? [String(data.summary).slice(0, 100)] : [],
      };
    }

    if (data.error) {
      return { title: "执行出错", details: [String(data.error).slice(0, 100)] };
    }

    return { title: "执行完成", details: [] };
  } catch {
    const text = str.slice(0, 150);
    return { title: "返回结果", details: text ? [text] : [] };
  }
}

interface AgentSidebarProps {
  steps: AgentStep[];
  isStreaming: boolean;
  visible: boolean;
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const stepVariants = {
  hidden: { opacity: 0, x: -16, scale: 0.95 },
  show: { opacity: 1, x: 0, scale: 1, transition: { type: "spring" as const, stiffness: 250, damping: 25 } },
};

export function AgentSidebar({ steps, isStreaming, visible }: AgentSidebarProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const prevLenRef = useRef(0);
  const [width, setWidth] = useState(320);
  const isResizing = useRef(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    const startX = e.clientX;
    const startWidth = width;

    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizing.current) return;
      const delta = startX - ev.clientX;
      const newWidth = Math.min(Math.max(startWidth + delta, 240), 500);
      setWidth(newWidth);
    };

    const onMouseUp = () => {
      isResizing.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, [width]);

  useEffect(() => {
    if (steps.length > prevLenRef.current) {
      setExpanded(new Set([steps.length - 1]));
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      });
    }
    prevLenRef.current = steps.length;
  }, [steps.length]);

  if (!visible) return null;

  const toggle = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div className="relative flex h-full flex-col glass-card border-l-0 rounded-none" style={{ width: `${width}px` }}>
      {/* Resize handle */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-indigo-400/30 transition-colors z-10 group"
        onMouseDown={handleMouseDown}
      >
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-8 rounded-full bg-white/5 group-hover:bg-indigo-400/40 transition-colors" />
      </div>

      {/* Header */}
      <div className="border-b border-white/5 bg-gradient-to-r from-indigo-500/5 to-violet-500/5">
        <div className="flex items-center gap-2.5 px-4 py-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 shadow-lg shadow-indigo-500/20">
            <Brain className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1">
            <span className="text-sm font-semibold text-[#e2e8f0]">Agent 思考链</span>
            {steps.length > 0 && (
              <p className="text-[10px] text-[#94a3b8]">
                {steps.filter(s => s.type === "tool_call").length} 次工具调用
                {isStreaming && " \u00b7 执行中..."}
              </p>
            )}
          </div>
          {isStreaming && <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />}
        </div>
        {/* Progress bar */}
        <AnimatePresence>
          {isStreaming && (
            <motion.div
              className="h-0.5 bg-white/5 overflow-hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <motion.div
                className="h-full bg-gradient-to-r from-indigo-500 to-violet-500"
                initial={{ x: "-100%" }}
                animate={{ x: "100%" }}
                transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                style={{ width: "60%" }}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Step list */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3">
        {/* Empty state: streaming */}
        {steps.length === 0 && isStreaming && (
          <motion.div
            className="flex flex-col items-center justify-center py-12 text-[#94a3b8]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <div className="flex gap-1.5 mb-3">
              <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-400 [animation-delay:0ms]" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-400 [animation-delay:200ms]" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-400 [animation-delay:400ms]" />
            </div>
            <p className="text-xs">Agent 正在思考...</p>
          </motion.div>
        )}

        {/* Empty state: idle */}
        {steps.length === 0 && !isStreaming && (
          <motion.div
            className="flex flex-col items-center justify-center py-16 text-[#94a3b8]"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
          >
            <div className="relative mb-4">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-violet-500/10 border border-indigo-500/20 flex items-center justify-center">
                <Brain className="h-8 w-8 text-indigo-400/50" />
              </div>
              <div className="absolute -bottom-1 -right-1 h-5 w-5 rounded-full bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/30 flex items-center justify-center">
                <Zap className="h-3 w-3 text-indigo-400" />
              </div>
            </div>
            <p className="text-xs font-medium text-[#94a3b8] mb-1">等待 Agent 启动</p>
            <p className="text-[10px] text-[#94a3b8]/60 text-center px-4">
              发送消息后，Agent 的决策过程将在此实时展示
            </p>
          </motion.div>
        )}

        {/* Timeline */}
        <div className="relative space-y-2">
          {steps.length > 1 && (
            <div className="absolute left-[15px] top-4 bottom-4 w-px bg-gradient-to-b from-indigo-500/40 via-violet-500/30 to-transparent" />
          )}

          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="show"
          >
            {steps.map((step, i) => {
              const isOpen = expanded.has(i);
              const meta = getToolMeta(step.tool);
              const argsStr = step.type === "tool_call" ? formatArgs(step.args) : "";
              const result = step.type === "tool_result" ? formatResultSummary(step.tool, step.content) : null;

              return (
                <motion.div
                  key={i}
                  className="relative flex items-start gap-3 pl-1"
                  variants={stepVariants}
                >
                  {/* Node icon */}
                  <div
                    className="relative z-10 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2"
                    style={{
                      borderColor: step.type === "tool_call" ? "rgba(99,102,241,0.4)" : "rgba(34,197,94,0.4)",
                      background: step.type === "tool_call"
                        ? "linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1))"
                        : "linear-gradient(135deg, rgba(34,197,94,0.1), rgba(16,185,129,0.1))",
                    }}
                  >
                    {step.type === "tool_call" ? (
                      <Zap className="h-3.5 w-3.5 text-indigo-400" />
                    ) : (
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                    )}
                  </div>

                  {/* Content card */}
                  <div className="min-w-0 flex-1">
                    <button
                      onClick={() => toggle(i)}
                      className="w-full rounded-xl glass-card px-3 py-2.5 text-left hover:bg-white/[0.04] transition-colors"
                    >
                      {/* Title row */}
                      <div className="flex items-center gap-2">
                        <span className="text-base">{meta.icon}</span>
                        <span className="text-xs font-medium text-[#e2e8f0]">
                          {step.type === "tool_call" ? (
                            <>正在{meta.label}</>
                          ) : (
                            <>{meta.label}完成</>
                          )}
                        </span>
                        <motion.svg
                          width="12"
                          height="12"
                          viewBox="0 0 12 12"
                          className="ml-auto shrink-0 text-[#94a3b8]"
                          animate={{ rotate: isOpen ? 180 : 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <path d="M3 4.5L6 7.5L9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </motion.svg>
                      </div>

                      {/* Tool description */}
                      <p className="mt-0.5 text-[10px] text-[#94a3b8]/60">{meta.desc}</p>

                      {/* Args summary (collapsed) */}
                      {step.type === "tool_call" && argsStr && !isOpen && (
                        <p className="mt-1 truncate text-[10px] text-indigo-300/60">参数: {argsStr}</p>
                      )}

                      {/* Result summary (collapsed) */}
                      {step.type === "tool_result" && result && !isOpen && (
                        <p className="mt-1 text-[10px] text-emerald-300/60">{result.title}</p>
                      )}
                    </button>

                    {/* Expanded details */}
                    <AnimatePresence>
                      {isOpen && (
                        <motion.div
                          className="mt-1 rounded-xl neu-inset px-3 py-2.5 text-[11px]"
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        >
                          {step.type === "tool_call" && (
                            <>
                              {argsStr ? (
                                <div className="text-[#94a3b8]">
                                  <span className="font-medium text-[#e2e8f0]">调用参数: </span>{argsStr}
                                </div>
                              ) : (
                                <div className="text-[#94a3b8]">无需参数</div>
                              )}
                            </>
                          )}
                          {step.type === "tool_result" && result && (
                            <div className="space-y-1">
                              <div className="font-medium text-emerald-400">{result.title}</div>
                              {result.details.map((d, j) => (
                                <div key={j} className="text-[#94a3b8] pl-2 border-l-2 border-emerald-500/30">{d}</div>
                              ))}
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>

          {/* Streaming wait indicator */}
          <AnimatePresence>
            {isStreaming && steps.length > 0 && (
              <motion.div
                className="relative flex items-center gap-3 pl-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-indigo-400/30 bg-indigo-500/5">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400/60" />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[#94a3b8]">Agent 思考中</span>
                  <span className="flex gap-0.5">
                    <span className="h-1 w-1 animate-bounce rounded-full bg-indigo-400/60 [animation-delay:0ms]" />
                    <span className="h-1 w-1 animate-bounce rounded-full bg-indigo-400/60 [animation-delay:150ms]" />
                    <span className="h-1 w-1 animate-bounce rounded-full bg-indigo-400/60 [animation-delay:300ms]" />
                  </span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
