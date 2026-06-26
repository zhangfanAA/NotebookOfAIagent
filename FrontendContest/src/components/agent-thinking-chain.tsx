"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, CheckCircle, Loader2, Zap } from "lucide-react";
import type { AgentStep } from "@/lib/types";

// 工具名中文映射
const TOOL_LABELS: Record<string, string> = {
  rag_query: "知识检索",
  list_documents: "列出文档",
  upload_document: "上传文档",
  delete_document: "删除文档",
  generate_mindmap: "生成思维导图",
  generate_quiz: "生成测验",
  check_quiz_answer: "判分",
  generate_flashcards: "生成闪卡",
  compare_documents: "对比文档",
};

function getToolLabel(tool: string): string {
  return TOOL_LABELS[tool] || tool;
}

function formatArgs(args?: Record<string, unknown>): string {
  if (!args || Object.keys(args).length === 0) return "";
  const parts: string[] = [];
  for (const [k, v] of Object.entries(args)) {
    if (k === "user_id" || k === "session_id") continue;
    const val = typeof v === "string" ? v : JSON.stringify(v);
    if (val.length > 60) {
      parts.push(`${k}="${val.slice(0, 60)}..."`);
    } else {
      parts.push(`${k}="${val}"`);
    }
  }
  return parts.join(", ");
}

function truncateContent(content?: string, max = 150): string {
  if (!content) return "";
  return content.length > max ? content.slice(0, max) + "..." : content;
}

interface AgentThinkingChainProps {
  steps: AgentStep[];
  isStreaming: boolean;
}

export function AgentThinkingChain({ steps, isStreaming }: AgentThinkingChainProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const prevLenRef = useRef(0);

  useEffect(() => {
    if (steps.length > prevLenRef.current) {
      setExpanded(new Set([steps.length - 1]));
    }
    prevLenRef.current = steps.length;
  }, [steps.length]);

  const toggle = (idx: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  if (steps.length === 0 && !isStreaming) return null;

  return (
    <motion.div
      className="mb-3 glass-card rounded-2xl p-4"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 200, damping: 22 }}
    >
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold text-indigo-300">
        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 shadow-lg shadow-indigo-500/20">
          <Brain className="h-3.5 w-3.5 text-white" />
        </div>
        <span>Agent 思考链</span>
        {isStreaming && <Loader2 className="h-3 w-3 animate-spin text-indigo-400" />}
      </div>

      <div className="relative">
        {/* Timeline connector */}
        {steps.length > 1 && (
          <div className="absolute left-[15px] top-4 bottom-4 w-px bg-gradient-to-b from-indigo-500/40 via-violet-500/30 to-transparent" />
        )}

        <div className="space-y-2">
          <AnimatePresence>
            {steps.map((step, i) => {
              const isOpen = expanded.has(i);
              const argsStr = step.type === "tool_call" ? formatArgs(step.args) : "";
              const contentSummary = step.type === "tool_result" ? truncateContent(step.content as string) : "";

              return (
                <motion.div
                  key={i}
                  className="relative flex items-start gap-3 pl-0"
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ type: "spring", stiffness: 250, damping: 25, delay: 0.05 }}
                >
                  {/* Node icon */}
                  <div className="relative z-10 mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center">
                    {step.type === "tool_call" ? (
                      <motion.div
                        className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/30"
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", stiffness: 500, damping: 25 }}
                      >
                        <Zap className="h-3.5 w-3.5 text-indigo-400" />
                      </motion.div>
                    ) : (
                      <motion.div
                        className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500/20 to-green-500/20 border border-emerald-500/30"
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", stiffness: 500, damping: 25 }}
                      >
                        <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                      </motion.div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1">
                    <button
                      onClick={() => toggle(i)}
                      className="flex w-full items-center gap-1.5 text-left text-sm hover:opacity-80 transition-opacity"
                    >
                      {step.type === "tool_call" ? (
                        <span className="font-medium text-[#e2e8f0]">
                          Agent 决定调用{" "}
                          <code className="rounded-lg bg-indigo-500/10 px-1.5 py-0.5 text-xs text-indigo-300 border border-indigo-500/20 font-mono">
                            {getToolLabel(step.tool)}
                          </code>
                        </span>
                      ) : (
                        <span className="font-medium text-[#e2e8f0]">
                          <code className="rounded-lg bg-emerald-500/10 px-1.5 py-0.5 text-xs text-emerald-300 border border-emerald-500/20 font-mono">
                            {getToolLabel(step.tool)}
                          </code>{" "}
                          返回结果
                        </span>
                      )}
                      <motion.svg
                        width="12"
                        height="12"
                        viewBox="0 0 12 12"
                        className="shrink-0 text-[#94a3b8] ml-auto"
                        animate={{ rotate: isOpen ? 180 : 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        <path d="M3 4.5L6 7.5L9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                      </motion.svg>
                    </button>

                    {/* Expanded details */}
                    <AnimatePresence>
                      {isOpen && (
                        <motion.div
                          className="mt-2 rounded-xl neu-inset px-3 py-2.5 text-xs text-[#94a3b8]"
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        >
                          {step.type === "tool_call" && argsStr && (
                            <div>参数: {argsStr}</div>
                          )}
                          {step.type === "tool_result" && step.content != null && (
                            <div className="max-h-32 overflow-y-auto whitespace-pre-wrap">{String(step.content)}</div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Collapsed summary */}
                    {!isOpen && step.type === "tool_call" && argsStr && (
                      <div className="mt-0.5 truncate text-xs text-[#94a3b8]/60">{argsStr}</div>
                    )}
                    {!isOpen && step.type === "tool_result" && contentSummary && (
                      <div className="mt-0.5 truncate text-xs text-[#94a3b8]/60">{contentSummary}</div>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>

          {/* Streaming indicator */}
          {isStreaming && steps.length === 0 && (
            <motion.div
              className="flex items-center gap-2 text-xs text-[#94a3b8]"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <div className="flex gap-1">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-400/60 [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-400/60 [animation-delay:200ms]" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-400/60 [animation-delay:400ms]" />
              </div>
              <span>Agent 正在思考...</span>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
