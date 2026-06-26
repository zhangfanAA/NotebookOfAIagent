"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, Check, ChevronDown, ChevronUp, BookOpen, Star } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import type { Message } from "@/lib/types";
import * as api from "@/lib/api";

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [showActions, setShowActions] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const isUser = message.role === "user";
  const isStreaming = !!message.isStreaming;
  const isThinking = isStreaming && message.content === "思考中...";
  const hasContent = !!message.content;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFavorite = async () => {
    try {
      await api.addFavorite("", message.content);
    } catch (e) {
      console.error("Failed to add favorite:", e);
    }
  };

  // 用户消息为空时不渲染
  if (isUser && !hasContent) return null;

  // 引用上标组件（用于完成阶段，带来源 tooltip）
  const CiteSup = ({ children, ...props }: React.HTMLAttributes<HTMLElement> & { children?: React.ReactNode }) => {
    const text = typeof children === "string" ? children : String(children);
    const m = text.match(/\[(\d+)\]/);
    if (m) {
      const idx = parseInt(m[1]) - 1;
      const src = message.sources?.[idx];
      return (
        <sup
          className="cite-ref cursor-pointer text-indigo-400 hover:text-indigo-300 transition-colors"
          title={src ? `${src.source} 第${src.page}页` : undefined}
          {...props}
        >
          {children}
        </sup>
      );
    }
    return <sup {...props}>{children}</sup>;
  };

  return (
    <motion.div
      className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
      initial={{ opacity: 0, x: isUser ? 20 : -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" as const }}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* AI 头像 */}
      {!isUser && (
        <motion.div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full glass-card text-indigo-400 text-sm font-medium"
          whileHover={{ scale: 1.1 }}
        >
          AI
        </motion.div>
      )}

      <div className={`max-w-[80%] ${isUser ? "order-first" : ""}`}>
        {/* 消息气泡 */}
        <div
          className={`
            rounded-2xl px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-lg shadow-indigo-500/20 ml-auto"
              : "glass-card text-[#e2e8f0]"
            }
          `}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : isThinking ? (
            /* 阶段 1: 思考中 — shimmer loading */
            <div className="shimmer-loading rounded-lg py-2 px-1">
              <div className="flex items-center gap-2 text-[#94a3b8]">
                <motion.span
                  className="inline-block h-2 w-2 rounded-full bg-indigo-500/60"
                  animate={{ scale: [1, 1.3, 1] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
                />
                <motion.span
                  className="inline-block h-2 w-2 rounded-full bg-indigo-500/60"
                  animate={{ scale: [1, 1.3, 1] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0.15 }}
                />
                <motion.span
                  className="inline-block h-2 w-2 rounded-full bg-indigo-500/60"
                  animate={{ scale: [1, 1.3, 1] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0.3 }}
                />
                <span className="ml-1 text-[#94a3b8]/80 text-xs">思考中...</span>
              </div>
            </div>
          ) : isStreaming ? (
            /* 阶段 2: 流式传输中 — 纯文本逐字显示 + 光标 */
            <div className="text-[#94a3b8] whitespace-pre-wrap break-words">
              {message.content}
              <motion.span
                className="inline-block w-0.5 h-4 bg-indigo-400/60 ml-0.5 align-text-bottom"
                animate={{ opacity: [1, 0, 1] }}
                transition={{ duration: 0.8, repeat: Infinity }}
              />
            </div>
          ) : (
            /* 阶段 3: 传输完毕 — ReactMarkdown 渲染 */
            <div className="markdown-content relative" ref={contentRef}>
              <ReactMarkdown
                remarkPlugins={[remarkMath, remarkGfm]}
                rehypePlugins={[rehypeKatex, rehypeRaw]}
                components={{ sup: CiteSup }}
              >
                {message.content.replace(/\[(\d+)\]/g, '<sup>[$1]</sup>')}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* 置信度标签 */}
        {!isUser && !isStreaming && message.confidence !== undefined && message.confidence !== null && (
          <motion.div
            className="mt-1.5 flex items-center gap-2"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Badge
              variant="outline"
              className={`text-xs border-0 ${
                message.confidence >= 0.7
                  ? "bg-emerald-500/15 text-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.2)]"
                  : message.confidence >= 0.4
                  ? "bg-amber-500/15 text-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.2)]"
                  : "bg-red-500/15 text-red-400 shadow-[0_0_8px_rgba(248,113,113,0.2)]"
              }`}
            >
              {message.confidence >= 0.7 ? "高置信" : message.confidence >= 0.4 ? "中置信" : "低置信"}{" "}
              {Math.round(message.confidence * 100)}%
            </Badge>
          </motion.div>
        )}

        {/* 操作按钮 — 仅在非流式状态下显示 */}
        {!isUser && !isStreaming && hasContent && (
          <AnimatePresence>
            {showActions && (
              <motion.div
                className="mt-1.5 flex items-center gap-1"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 5 }}
                transition={{ duration: 0.15 }}
              >
                <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-[#94a3b8] hover:text-indigo-400" onClick={handleCopy}>
                    {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-[#94a3b8] hover:text-amber-400" onClick={handleFavorite}>
                    <Star className="h-3.5 w-3.5" />
                  </Button>
                </motion.div>
                {message.sources && message.sources.length > 0 && (
                  <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1 text-xs text-[#94a3b8] hover:text-indigo-400"
                      onClick={() => setShowSources(!showSources)}
                    >
                      <BookOpen className="h-3.5 w-3.5" />
                      引用来源 ({message.sources.length})
                      {showSources ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    </Button>
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        )}

        {/* 引用来源展开 */}
        <AnimatePresence>
          {!isUser && !isStreaming && showSources && message.sources && (
            <motion.div
              className="mt-2 space-y-1.5"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: "easeInOut" as const }}
            >
              {message.sources.map((src, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="rounded-xl glass-card px-3 py-2 text-xs glow-border"
                >
                  <div className="flex items-center gap-2 font-medium">
                    <span className="text-indigo-400">{i + 1}.</span>
                    <span className="text-[#e2e8f0]">{src.source}</span>
                    <span className="text-[#94a3b8]">第{src.page}页</span>
                    <Badge variant="outline" className="ml-auto text-[10px] border-indigo-500/30 text-indigo-300 bg-indigo-500/10">
                      {Math.round(src.score * 100)}%
                    </Badge>
                  </div>
                  <p className="mt-1 text-[#94a3b8] line-clamp-2">{src.content}</p>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 用户头像 */}
      {isUser && (
        <motion.div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-white text-xs font-medium"
          whileHover={{ scale: 1.1 }}
        >
          U
        </motion.div>
      )}
    </motion.div>
  );
}
