"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Square, Map, FileQuestion, BookOpen, Brain, ChevronUp, ChevronDown } from "lucide-react";
import * as api from "@/lib/api";

interface InputBarProps {
  onSend: (question: string, memoryMode: boolean, agentMode: boolean) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled: boolean;
}

export function InputBar({ onSend, onStop, isStreaming, disabled }: InputBarProps) {
  const [input, setInput] = useState("");
  const [memoryMode, setMemoryMode] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("memory_mode") === "true";
  });
  const [showQuickActions, setShowQuickActions] = useState(true);
  const [agentMode, setAgentMode] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("agent_mode") === "true";
  });
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
    }
  }, [input]);

  const handleSubmit = useCallback(() => {
    if (!input.trim() || isStreaming || disabled) return;
    const currentAgentMode = typeof window !== "undefined" && localStorage.getItem("agent_mode") === "true";
    onSend(input.trim(), memoryMode, currentAgentMode);
    setInput("");
  }, [input, isStreaming, disabled, onSend, memoryMode]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleQuickAction = (prefix: string) => {
    const text = input.trim();
    if (text) {
      const currentAgentMode = typeof window !== "undefined" && localStorage.getItem("agent_mode") === "true";
      onSend(`${prefix}: ${text}`, memoryMode, currentAgentMode);
      setInput("");
    }
  };

  const toggleMemoryMode = () => {
    const next = !memoryMode;
    setMemoryMode(next);
    localStorage.setItem("memory_mode", String(next));
  };

  return (
    <div className="border-t glass-card px-4 py-3">
      <div className="mx-auto max-w-3xl">
        {/* Quick action toggle */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 gap-1 text-xs rounded-lg transition-all ${
                  memoryMode
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                    : "text-[#94a3b8] hover:text-[#e2e8f0]"
                }`}
                disabled={disabled || isStreaming}
                onClick={toggleMemoryMode}
              >
                <Brain className="h-3 w-3" />
                {memoryMode ? "记忆中" : "记忆模式"}
                {memoryMode && (
                  <motion.span
                    className="inline-block h-1.5 w-1.5 rounded-full bg-indigo-400"
                    animate={{ opacity: [1, 0.4, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                )}
              </Button>
            </motion.div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-[#94a3b8] hover:text-[#e2e8f0]"
            onClick={() => setShowQuickActions(!showQuickActions)}
          >
            {showQuickActions ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </Button>
        </div>

        {/* Quick action buttons */}
        <AnimatePresence>
          {showQuickActions && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" as const }}
              className="overflow-hidden"
            >
              <div className="mb-2 flex gap-1.5">
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1 text-xs neu-button border-0 text-[#94a3b8] hover:text-indigo-300"
                    disabled={disabled || isStreaming || !input.trim()}
                    onClick={() => handleQuickAction("请帮我生成思维导图")}
                  >
                    <Map className="h-3 w-3" />
                    导图
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1 text-xs neu-button border-0 text-[#94a3b8] hover:text-purple-300"
                    disabled={disabled || isStreaming || !input.trim()}
                    onClick={() => handleQuickAction("请帮我生成重点笔记")}
                  >
                    <BookOpen className="h-3 w-3" />
                    笔记
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1 text-xs neu-button border-0 text-[#94a3b8] hover:text-cyan-300"
                    disabled={disabled || isStreaming || !input.trim()}
                    onClick={() => handleQuickAction("请帮我出几道测验题")}
                  >
                    <FileQuestion className="h-3 w-3" />
                    测验
                  </Button>
                </motion.div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input area */}
        <motion.div
          className={`flex items-end gap-2 rounded-2xl glass-input p-2 transition-all ${
            agentMode && !disabled ? "glow-border" : ""
          }`}
          animate={
            agentMode && !disabled
              ? { boxShadow: ["0 0 0px rgba(99,102,241,0)", "0 0 12px rgba(99,102,241,0.15)", "0 0 0px rgba(99,102,241,0)"] }
              : {}
          }
          transition={agentMode && !disabled ? { duration: 2, repeat: Infinity, ease: "easeInOut" as const } : {}}
        >
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? "请先选择或创建会话..." : "输入你的问题... (Shift+Enter 换行)"}
            disabled={disabled}
            className="min-h-[40px] max-h-[160px] resize-none border-0 bg-transparent p-2 text-sm shadow-none focus-visible:ring-0 text-[#e2e8f0] placeholder:text-[#94a3b8]/50"
            rows={1}
          />
          {isStreaming ? (
            <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
              <Button
                size="icon"
                variant="destructive"
                className="h-9 w-9 shrink-0 rounded-xl"
                onClick={onStop}
              >
                <Square className="h-4 w-4" />
              </Button>
            </motion.div>
          ) : (
            <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
              <Button
                size="icon"
                className="h-9 w-9 shrink-0 rounded-xl relative overflow-hidden group"
                disabled={disabled || !input.trim()}
                onClick={handleSubmit}
              >
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                <Send className="h-4 w-4 relative z-10" />
              </Button>
            </motion.div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
