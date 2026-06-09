"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Square, Map, FileQuestion, BookOpen } from "lucide-react";
import * as api from "@/lib/api";

interface InputBarProps {
  onSend: (question: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled: boolean;
}

export function InputBar({ onSend, onStop, isStreaming, disabled }: InputBarProps) {
  const [input, setInput] = useState("");
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
    onSend(input.trim());
    setInput("");
  }, [input, isStreaming, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleQuickAction = (prefix: string) => {
    const text = input.trim();
    if (text) {
      onSend(`${prefix}: ${text}`);
      setInput("");
    }
  };

  return (
    <div className="border-t bg-background/80 backdrop-blur-xl px-4 py-3">
      <div className="mx-auto max-w-3xl">
        {/* Quick action buttons */}
        <div className="mb-2 flex gap-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-xs"
            disabled={disabled || isStreaming || !input.trim()}
            onClick={() => handleQuickAction("请帮我生成思维导图")}
          >
            <Map className="h-3 w-3" />
            🗺️ 导图
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-xs"
            disabled={disabled || isStreaming || !input.trim()}
            onClick={() => handleQuickAction("请帮我生成重点笔记")}
          >
            <BookOpen className="h-3 w-3" />
            📝 笔记
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-xs"
            disabled={disabled || isStreaming || !input.trim()}
            onClick={() => handleQuickAction("请帮我出几道测验题")}
          >
            <FileQuestion className="h-3 w-3" />
            📝 测验
          </Button>
        </div>

        {/* Input area */}
        <div className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-sm transition-shadow focus-within:shadow-md focus-within:border-primary/30">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? "请先选择或创建会话..." : "输入你的问题... (Shift+Enter 换行)"}
            disabled={disabled}
            className="min-h-[40px] max-h-[160px] resize-none border-0 bg-transparent p-2 text-sm shadow-none focus-visible:ring-0"
            rows={1}
          />
          {isStreaming ? (
            <Button
              size="icon"
              variant="destructive"
              className="h-9 w-9 shrink-0 rounded-xl"
              onClick={onStop}
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              className="h-9 w-9 shrink-0 rounded-xl"
              disabled={disabled || !input.trim()}
              onClick={handleSubmit}
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
