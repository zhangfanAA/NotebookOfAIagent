"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Database, Search, Clock, ChevronDown, Loader2 } from "lucide-react";
import * as api from "@/lib/api";
import type { MemoryStats, MemoryRecord } from "@/lib/api";

function useAnimatedCounter(target: number, duration = 800) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const animate = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, duration]);
  return value;
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.97 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring" as const, stiffness: 250, damping: 25 } },
};

interface MemoryPanelProps {
  sessionId: string | null;
  visible: boolean;
}

export function MemoryPanel({ sessionId, visible }: MemoryPanelProps) {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showRecords, setShowRecords] = useState(false);

  const sessionCount = useAnimatedCounter(stats?.session_records ?? 0);
  const totalCount = useAnimatedCounter(stats?.total_records ?? 0);

  const loadStats = useCallback(async () => {
    try {
      const data = await api.getMemoryStats(sessionId || undefined);
      setStats(data);
    } catch {}
  }, [sessionId]);

  const loadRecords = useCallback(async () => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const data = await api.getMemoryRecent(sessionId);
      setRecords(data.records || []);
    } catch {} finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (visible) loadStats();
  }, [visible, loadStats]);

  useEffect(() => {
    if (visible && sessionId && showRecords) loadRecords();
  }, [visible, sessionId, showRecords, loadRecords]);

  if (!visible) return null;

  const formatTime = (ts: number) => {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="border-t border-white/5">
      {/* Collapse header */}
      <motion.button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-xs font-medium text-[#94a3b8] hover:text-[#e2e8f0] transition-colors"
        whileHover={{ backgroundColor: "rgba(255,255,255,0.02)" }}
      >
        <Database className="h-3.5 w-3.5 text-indigo-400" />
        <span>对话记忆</span>
        {stats && (
          <span className="ml-auto flex items-center gap-1.5">
            <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-300 border border-indigo-500/20">
              本会话 {sessionCount} 条
            </span>
            <motion.svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              className="text-[#94a3b8]"
              animate={{ rotate: expanded ? 180 : 0 }}
              transition={{ duration: 0.2 }}
            >
              <path d="M3 4.5L6 7.5L9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </motion.svg>
          </span>
        )}
      </motion.button>

      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            className="border-t border-white/5 px-4 py-3 space-y-3"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          >
            {/* Storage status */}
            <motion.div
              className="glass-card rounded-xl p-3"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
            >
              <div className="flex items-center gap-2 mb-2.5">
                <div className="flex h-5 w-5 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/20">
                  <Database className="h-3 w-3 text-indigo-400" />
                </div>
                <span className="text-xs font-medium text-[#e2e8f0]">向量存储状态</span>
              </div>
              <div className="neu-inset rounded-lg p-2.5 grid grid-cols-2 gap-2 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-[#94a3b8]">本会话记忆</span>
                  <span className="font-medium text-[#e2e8f0]">{sessionCount} 条</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#94a3b8]">用户总记忆</span>
                  <span className="font-medium text-[#e2e8f0]">{totalCount} 条</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#94a3b8]">集合名称</span>
                  <span className="font-mono text-[10px] text-[#e2e8f0]">{stats?.collection_name ?? "-"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#94a3b8]">向量维度</span>
                  <span className="font-medium text-[#e2e8f0]">512</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#94a3b8]">嵌入模型</span>
                  <span className="font-mono text-[10px] text-[#e2e8f0]">bge-small-zh</span>
                </div>
              </div>
            </motion.div>

            {/* Retrieval records */}
            <motion.div
              className="glass-card rounded-xl p-3"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <button
                onClick={() => setShowRecords(!showRecords)}
                className="flex w-full items-center gap-2 mb-2"
              >
                <div className="flex h-5 w-5 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/20">
                  <Search className="h-3 w-3 text-violet-400" />
                </div>
                <span className="text-xs font-medium text-[#e2e8f0]">本会话记忆记录</span>
                <span className="ml-auto text-[10px] text-[#94a3b8] flex items-center gap-0.5">
                  {showRecords ? "收起" : "展开"}
                  <motion.svg
                    width="12"
                    height="12"
                    viewBox="0 0 12 12"
                    className="text-[#94a3b8]"
                    animate={{ rotate: showRecords ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <path d="M3 4.5L6 7.5L9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </motion.svg>
                </span>
              </button>

              <AnimatePresence>
                {showRecords && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  >
                    {isLoading ? (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                      </div>
                    ) : records.length === 0 ? (
                      <div className="py-4 text-center text-[11px] text-[#94a3b8]">本会话暂无记忆记录</div>
                    ) : (
                      <motion.div
                        className="space-y-2 max-h-60 overflow-y-auto"
                        variants={containerVariants}
                        initial="hidden"
                        animate="show"
                      >
                        {records.map((r, i) => (
                          <motion.div
                            key={i}
                            className="rounded-xl neu-inset px-3 py-2.5 text-[11px]"
                            variants={itemVariants}
                          >
                            <div className="flex items-start gap-1.5 mb-1">
                              <span className="shrink-0 mt-0.5 rounded-md bg-indigo-500/10 px-1.5 py-0.5 text-[9px] text-indigo-300 font-bold border border-indigo-500/20">
                                Q
                              </span>
                              <span className="text-[#e2e8f0]">{r.question.slice(0, 80)}</span>
                            </div>
                            <div className="flex items-start gap-1.5 mb-1">
                              <span className="shrink-0 mt-0.5 rounded-md bg-emerald-500/10 px-1.5 py-0.5 text-[9px] text-emerald-300 font-bold border border-emerald-500/20">
                                A
                              </span>
                              <span className="text-[#94a3b8]">{r.answer.slice(0, 100)}</span>
                            </div>
                            <div className="flex items-center gap-2 mt-1 text-[10px] text-[#94a3b8]/50">
                              <Clock className="h-2.5 w-2.5" />
                              <span>{formatTime(r.timestamp)}</span>
                              {r.sources && <span>\u00b7 引用: {r.sources.slice(0, 30)}</span>}
                            </div>
                          </motion.div>
                        ))}
                      </motion.div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
