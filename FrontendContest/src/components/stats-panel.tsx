"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BarChart3, TrendingUp, AlertTriangle, BookOpen, MessageSquare } from "lucide-react";
import type { LearningProgress } from "@/lib/types";
import * as api from "@/lib/api";

// Animated number counter hook
function useAnimatedCounter(target: number, duration = 1200) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const start = performance.now();
    const from = 0;
    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setValue(Math.round(from + (target - from) * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return value;
}

interface StatsPanelProps {
  sessionId: string | null;
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring" as const, stiffness: 200, damping: 20 } },
};

export function StatsPanel({ sessionId }: StatsPanelProps) {
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [weakTopics, setWeakTopics] = useState<{ topic: string; question_count: number }[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [documents, setDocuments] = useState<{ name: string; chunks: number }[]>([]);

  const loadData = useCallback(async () => {
    if (!sessionId) return;
    try {
      const [progressRes, weakRes, topicsRes, docsRes] = await Promise.all([
        api.getLearningProgress(sessionId),
        api.getWeakTopics(sessionId),
        api.getSessionTopics(sessionId),
        api.getDocuments(),
      ]);
      console.log("[Stats] progress:", progressRes, "weak:", weakRes, "topics:", topicsRes);
      setProgress(progressRes);
      setWeakTopics(weakRes.weak_topics || []);
      setTopics((topicsRes.topics || []).map((t: { topic?: string } | string) => typeof t === "string" ? t : t.topic || ""));
      setDocuments(docsRes.documents.map((d) => ({ name: d.file_name, chunks: d.chunks_count })));
    } catch (e) {
      console.error("Failed to load stats:", e);
    }
  }, [sessionId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalQuestions = progress?.total_questions ?? 0;
  const avgConfidence = progress ? Math.round(progress.avg_confidence * 100) : 0;
  const knowledgeGaps = progress?.knowledge_gaps?.length ?? 0;
  const docCount = documents.length;

  const animatedQuestions = useAnimatedCounter(totalQuestions);
  const animatedConfidence = useAnimatedCounter(avgConfidence);
  const animatedGaps = useAnimatedCounter(knowledgeGaps);
  const animatedDocs = useAnimatedCounter(docCount);

  const maxChunks = Math.max(...documents.map((x) => x.chunks), 1);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <motion.h1
          className="text-2xl font-bold text-gradient"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          学习统计
        </motion.h1>

        {/* Overview cards */}
        <motion.div
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
          variants={containerVariants}
          initial="hidden"
          animate="show"
        >
          <StatCard
            icon={<MessageSquare className="h-4 w-4" />}
            label="提问次数"
            value={animatedQuestions}
            suffix=""
            color="from-indigo-500 to-violet-500"
            delay={0}
          />
          <StatCard
            icon={<TrendingUp className="h-4 w-4" />}
            label="平均置信度"
            value={animatedConfidence}
            suffix="%"
            color="from-cyan-500 to-blue-500"
            delay={0.1}
          />
          <StatCard
            icon={<AlertTriangle className="h-4 w-4" />}
            label="知识缺口"
            value={animatedGaps}
            suffix=""
            color="from-amber-500 to-orange-500"
            delay={0.2}
          />
          <StatCard
            icon={<BookOpen className="h-4 w-4" />}
            label="文档数"
            value={animatedDocs}
            suffix=""
            color="from-emerald-500 to-teal-500"
            delay={0.3}
          />
        </motion.div>

        {/* Weak topics */}
        <AnimatePresence>
          {weakTopics.length > 0 && (
            <motion.div
              className="glass-card rounded-2xl p-5"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ delay: 0.3 }}
            >
              <h3 className="text-sm font-semibold mb-3 text-[#e2e8f0] flex items-center gap-2">
                <span className="text-amber-400">&#9888;&#65039;</span>
                薄弱知识点
              </h3>
              <div className="space-y-2">
                {weakTopics.map((t, i) => (
                  <motion.div
                    key={i}
                    className="flex items-center justify-between rounded-xl px-4 py-2.5 neu-inset"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.35 + i * 0.05 }}
                  >
                    <span className="text-sm text-[#e2e8f0]">{t.topic}</span>
                    <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 font-medium border border-amber-500/20">
                      {t.question_count} 次
                    </span>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Topics covered */}
        <AnimatePresence>
          {topics.length > 0 && (
            <motion.div
              className="glass-card rounded-2xl p-5"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ delay: 0.4 }}
            >
              <h3 className="text-sm font-semibold mb-3 text-[#e2e8f0] flex items-center gap-2">
                <span>&#128218;</span>
                已学话题
              </h3>
              <motion.div
                className="flex flex-wrap gap-1.5"
                variants={containerVariants}
                initial="hidden"
                animate="show"
              >
                {topics.map((t, i) => (
                  <motion.span
                    key={i}
                    className="text-xs px-2.5 py-1 rounded-full bg-primary/10 text-primary-foreground/80 border border-primary/20 font-medium"
                    variants={itemVariants}
                  >
                    {t}
                  </motion.span>
                ))}
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Document chunks chart */}
        <AnimatePresence>
          {documents.length > 0 && (
            <motion.div
              className="glass-card rounded-2xl p-5"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ delay: 0.5 }}
            >
              <h3 className="text-sm font-semibold mb-3 text-[#e2e8f0] flex items-center gap-2">
                <span>&#128196;</span>
                文档分块统计
              </h3>
              <div className="neu-inset rounded-xl p-4 space-y-3">
                {documents.map((d, i) => {
                  const pct = (d.chunks / maxChunks) * 100;
                  return (
                    <motion.div
                      key={i}
                      className="flex items-center gap-3"
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.55 + i * 0.05 }}
                    >
                      <span className="w-32 truncate text-sm text-[#94a3b8]">{d.name}</span>
                      <div className="flex-1 h-3 rounded-full bg-white/5 overflow-hidden">
                        <motion.div
                          className="h-full rounded-full"
                          style={{
                            background: "linear-gradient(90deg, #6366f1, #8b5cf6, #a78bfa)",
                          }}
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.8, delay: 0.6 + i * 0.08, ease: "easeOut" as const }}
                        />
                      </div>
                      <span className="text-xs text-[#94a3b8] w-12 text-right font-mono">{d.chunks}</span>
                    </motion.div>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {!sessionId && (
          <motion.div
            className="flex flex-col items-center justify-center py-16 text-[#94a3b8]"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <BarChart3 className="h-16 w-16 mb-4 opacity-20" />
            <p className="text-sm">请先选择一个会话</p>
          </motion.div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  suffix,
  color,
  delay,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  suffix: string;
  color: string;
  delay: number;
}) {
  return (
    <motion.div
      className="glass-card glow-border rounded-2xl p-4 relative overflow-hidden group"
      variants={itemVariants}
    >
      {/* Gradient accent bar at top */}
      <div className={`absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r ${color} opacity-60`} />

      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-[#94a3b8]">{label}</span>
        <div className={`flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br ${color} text-white shadow-lg`}>
          {icon}
        </div>
      </div>
      <div className="text-2xl font-bold text-[#e2e8f0]">
        {value}
        {suffix && <span className="text-base ml-0.5 text-[#94a3b8]">{suffix}</span>}
      </div>
    </motion.div>
  );
}
