"use client";

import { useRef, useEffect, useCallback, useState } from "react";
import { MessageBubble } from "@/components/message-bubble";
import { InputBar } from "@/components/input-bar";
import type { Message, Source } from "@/lib/types";
import * as api from "@/lib/api";

interface ChatAreaProps {
  sessionId: string | null;
  messages: Message[];
  setMessages: (msgs: Message[] | ((prev: Message[]) => Message[])) => void;
  onMobileMenuOpen: () => void;
  pendingQuestion?: string | null;
  onPendingQuestionConsumed?: () => void;
}

export function ChatArea({ sessionId, messages, setMessages, onMobileMenuOpen, pendingQuestion, onPendingQuestionConsumed }: ChatAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

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

  /** 将最后一条助手消息标记为完成 */
  const finalizeLastMessage = useCallback((sm: typeof setMessages, extra?: Partial<Message>) => {
    sm((prev) => {
      const updated = [...prev];
      const lastIdx = updated.length - 1;
      if (lastIdx >= 0 && updated[lastIdx].role === "assistant") {
        const last = updated[lastIdx];
        // 如果还在"思考中"，说明没有任何 token 到达
        const content = last.content === "思考中..." ? (extra?.content || "（无响应）") : last.content;
        updated[lastIdx] = { ...last, ...extra, content, isStreaming: false };
      }
      return updated;
    });
  }, []);

  /** 核心发送函数 */
  const handleSend = useCallback((question: string, memoryMode: boolean = false) => {
    if (!sessionId || !question.trim()) return;
    if (abortRef.current) return;

    const sm = setMessagesRef.current;

    // 1. 添加用户消息
    sm((prev) => [...prev, { role: "user", content: question }]);

    // 2. 添加助手占位消息
    sm((prev) => [...prev, { role: "assistant", content: "思考中...", isStreaming: true }]);

    setIsStreaming(true);

    // 3. 开始流式请求
    const abort = api.chatStream(
      question,
      sessionId,
      // onChunk — 处理后端 SSE 数据
      (chunk) => {
        if (chunk.type === "token") {
          // 后端: {"type": "token", "data": "token文本"}
          const token = typeof chunk.data === "string" ? chunk.data : chunk.content || "";
          if (!token) return;
          sm((prev) => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            const last = updated[lastIdx];
            if (lastIdx < 0 || last.role !== "assistant") return prev;
            // 第一个 token: 替换 "思考中..."
            const newContent = last.content === "思考中..." ? token : last.content + token;
            updated[lastIdx] = { ...last, content: newContent, isStreaming: true };
            return updated;
          });
        } else if (chunk.type === "result") {
          // 后端: {"type": "result", "data": {"sources": [...], "confidence": 0.8}}
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
        } else if (chunk.type === "error") {
          // 后端: {"type": "error", "data": "错误信息"}
          const errorMsg = typeof chunk.data === "string" ? chunk.data : chunk.content || "出错了";
          finalizeLastMessage(sm, { content: `⚠️ ${errorMsg}` });
        }
      },
      // onError
      (err) => {
        const msg = err.message || "";
        if (msg.includes("余额不足") || msg.includes("402")) {
          // 移除占位消息
          sm((prev) => prev.filter((_, i) => i < prev.length - 1 || prev[i].role !== "assistant" || prev[i].content !== "思考中..."));
          alert("余额不足，请联系管理员充值后再试");
        } else {
          finalizeLastMessage(sm, { content: `⚠️ 连接失败: ${msg}` });
        }
        abortRef.current = null;
        setIsStreaming(false);
      },
      // onDone
      () => {
        finalizeLastMessage(sm);
        abortRef.current = null;
        setIsStreaming(false);
      },
      memoryMode
    );

    abortRef.current = abort;
  }, [sessionId, finalizeLastMessage]);

  // 处理来自思维导图等组件的 pending 问题
  useEffect(() => {
    if (pendingQuestion && sessionId && !abortRef.current) {
      handleSend(pendingQuestion);
      onPendingQuestionConsumed?.();
    }
  }, [pendingQuestion, sessionId, handleSend, onPendingQuestionConsumed]);

  const handleStop = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    finalizeLastMessage(setMessagesRef.current);
    setIsStreaming(false);
  }, [finalizeLastMessage]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
            <div className="text-6xl mb-4">📚</div>
            <h2 className="text-xl font-semibold mb-2">智能学习助手</h2>
            <p className="text-sm">上传文件，开始你的学习之旅</p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((msg, i) => (
              <MessageBubble key={`${sessionId}-${i}`} message={msg} />
            ))}
          </div>
        )}
      </div>

      <InputBar
        onSend={handleSend}
        onStop={handleStop}
        isStreaming={isStreaming}
        disabled={!sessionId}
      />
    </div>
  );
}
