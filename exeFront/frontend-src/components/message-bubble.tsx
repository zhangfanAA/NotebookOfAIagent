"use client";

import { useState, useRef, useEffect, useCallback } from "react";
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

// 匹配 [来源：xxx.pdf 第XX页]
const CITATION_RE = /\[来源[：:]\s*(.+?)\s+第(\d+)页\]/g;

/** markdown 转 HTML 后替换引用为行内 <sup> */
function markdownToHtmlWithCitations(md: string): string {
  // 简易 markdown → HTML（覆盖常用语法）
  let html = md
    // 代码块
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
    // 行内代码
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // 加粗
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 斜体
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // 标题
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // 表格处理
  html = html.replace(/^(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)/gm, (_match, header, sep, body) => {
    const ths = header.split("|").filter((c: string) => c.trim()).map((c: string) => `<th>${c.trim()}</th>`).join("");
    const rows = body.trim().split("\n").map((row: string) => {
      const tds = row.split("|").filter((c: string) => c.trim()).map((c: string) => `<td>${c.trim()}</td>`).join("");
      return `<tr>${tds}</tr>`;
    }).join("");
    return `<table><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table>`;
  });

  // 引用块
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

  // 无序列表
  html = html.replace(/^(?:- (.+)\n?)+/gm, (match) => {
    const items = match.trim().split("\n").map(line => `<li>${line.replace(/^- /, "")}</li>`).join("");
    return `<ul>${items}</ul>`;
  });

  // 段落（剩余的非空行）
  html = html.replace(/^(?!<[a-z/])(.+)$/gm, "<p>$1</p>");

  // 替换引用为行内 sup
  let citeIndex = 0;
  html = html.replace(CITATION_RE, (_match, source, page) => {
    const idx = citeIndex++;
    return `<sup class="cite-ref" data-idx="${idx}" data-source="${source}" data-page="${page}">[${idx + 1}]</sup>`;
  });

  return html;
}

interface MessageBubbleProps {
  message: Message;
}

function CitationContent({ containerRef }: { containerRef: React.RefObject<HTMLDivElement | null> }) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);

  const handleMouseOver = useCallback((e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.classList.contains("cite-ref")) {
      const source = target.getAttribute("data-source") || "";
      const page = target.getAttribute("data-page") || "";
      const rect = target.getBoundingClientRect();
      const parentRect = containerRef.current?.getBoundingClientRect();
      if (parentRect) {
        setTooltip({
          x: rect.left - parentRect.left + rect.width / 2,
          y: rect.top - parentRect.top,
          text: `${source} 第${page}页`,
        });
      }
    }
  }, [containerRef]);

  const handleMouseOut = useCallback((e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.classList.contains("cite-ref")) {
      setTooltip(null);
    }
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener("mouseover", handleMouseOver);
    el.addEventListener("mouseout", handleMouseOut);
    return () => {
      el.removeEventListener("mouseover", handleMouseOver);
      el.removeEventListener("mouseout", handleMouseOut);
    };
  }, [containerRef, handleMouseOver, handleMouseOut]);

  if (!tooltip) return null;
  return (
    <div
      className="absolute z-50 whitespace-nowrap rounded-lg bg-foreground px-3 py-1.5 text-xs text-background shadow-lg pointer-events-none"
      style={{ left: tooltip.x, top: tooltip.y, transform: "translate(-50%, -100%) translateY(-8px)" }}
    >
      {tooltip.text}
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [showSources, setShowSources] = useState(false);
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

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {/* AI 头像 */}
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-sm">
          AI
        </div>
      )}

      <div className={`max-w-[80%] ${isUser ? "order-first" : ""}`}>
        {/* 消息气泡 */}
        <div
          className={`
            rounded-2xl px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? "bg-primary text-primary-foreground ml-auto"
              : "bg-card border shadow-sm"
            }
          `}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : isThinking ? (
            /* 阶段 1: 思考中 — 灰色脉冲动画 */
            <div className="flex items-center gap-1.5 text-muted-foreground animate-pulse">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-bounce" style={{ animationDelay: "300ms" }} />
              <span className="ml-1 text-muted-foreground/80">思考中...</span>
            </div>
          ) : isStreaming ? (
            /* 阶段 2: 流式传输中 — 灰色文字 + 光标 */
            <div className="markdown-content text-muted-foreground/80">
              <ReactMarkdown remarkPlugins={[remarkMath, remarkGfm]} rehypePlugins={[rehypeKatex, rehypeRaw]}>
                {message.content}
              </ReactMarkdown>
              <span className="inline-block w-0.5 h-4 bg-primary/60 animate-pulse ml-0.5 align-text-bottom" />
            </div>
          ) : (
            /* 阶段 3: 传输完毕 — 引用替换为行内上标 */
            <div className="markdown-content relative" ref={contentRef}>
              <div
                dangerouslySetInnerHTML={{
                  __html: markdownToHtmlWithCitations(message.content),
                }}
              />
              <CitationContent containerRef={contentRef} />
            </div>
          )}
        </div>

        {/* 置信度标签 */}
        {!isUser && !isStreaming && message.confidence !== undefined && message.confidence !== null && (
          <div className="mt-1.5 flex items-center gap-2">
            <Badge
              variant="outline"
              className={`text-xs ${
                message.confidence >= 0.7
                  ? "text-green-600 border-green-200 bg-green-50 dark:text-green-400 dark:border-green-800 dark:bg-green-950"
                  : message.confidence >= 0.4
                  ? "text-yellow-600 border-yellow-200 bg-yellow-50 dark:text-yellow-400 dark:border-yellow-800 dark:bg-yellow-950"
                  : "text-red-600 border-red-200 bg-red-50 dark:text-red-400 dark:border-red-800 dark:bg-red-950"
              }`}
            >
              {message.confidence >= 0.7 ? "高置信" : message.confidence >= 0.4 ? "中置信" : "低置信"}{" "}
              {Math.round(message.confidence * 100)}%
            </Badge>
          </div>
        )}

        {/* 操作按钮 — 仅在非流式状态下显示 */}
        {!isUser && !isStreaming && hasContent && (
          <div className="mt-1.5 flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleCopy}>
              {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
            </Button>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleFavorite}>
              <Star className="h-3.5 w-3.5" />
            </Button>
            {message.sources && message.sources.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 text-xs text-muted-foreground"
                onClick={() => setShowSources(!showSources)}
              >
                <BookOpen className="h-3.5 w-3.5" />
                引用来源 ({message.sources.length})
                {showSources ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </Button>
            )}
          </div>
        )}

        {/* 引用来源展开 */}
        {!isUser && !isStreaming && showSources && message.sources && (
          <div className="mt-2 space-y-1.5">
            {message.sources.map((src, i) => (
              <div key={i} className="rounded-xl border bg-card/50 px-3 py-2 text-xs shadow-sm">
                <div className="flex items-center gap-2 font-medium">
                  <span className="text-primary">{i + 1}.</span>
                  <span>{src.source}</span>
                  <span className="text-muted-foreground">第{src.page}页</span>
                  <Badge variant="outline" className="ml-auto text-[10px]">
                    {Math.round(src.score * 100)}%
                  </Badge>
                </div>
                <p className="mt-1 text-muted-foreground line-clamp-2">{src.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
          U
        </div>
      )}
    </div>
  );
}
