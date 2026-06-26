"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, GitCompare, CheckCircle, XCircle } from "lucide-react";
import * as api from "@/lib/api";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 200, damping: 22 } },
};

export function ComparePanel() {
  const [documents, setDocuments] = useState<{ id: number; name: string }[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [focus, setFocus] = useState("");
  const [result, setResult] = useState<{ similarities: string[]; differences: string[]; summary: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getDocuments().then((res) => {
      setDocuments(res.documents.filter((d) => d.status === "ready").map((d) => ({ id: d.id, name: d.file_name })));
    }).catch(() => {});
  }, []);

  const handleCompare = useCallback(async () => {
    if (selectedDocs.length < 2) return;
    setIsLoading(true);
    setError("");
    try {
      const res = await api.compareDocuments(selectedDocs, focus);
      if (res.status === "success") {
        setResult({ similarities: res.similarities || [], differences: res.differences || [], summary: res.summary || "" });
      } else {
        setError("对比失败");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [selectedDocs, focus]);

  const toggleDoc = (docName: string) => {
    setSelectedDocs((prev) =>
      prev.includes(docName) ? prev.filter((d) => d !== docName) : [...prev, docName]
    );
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <motion.h1
          className="text-2xl font-bold text-gradient"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          文档对比
        </motion.h1>

        {/* Document selector */}
        <motion.div
          className="glass-card rounded-2xl p-5 space-y-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <h3 className="text-sm font-semibold text-[#e2e8f0]">选择文档（至少 2 个）</h3>

          <div className="flex flex-wrap gap-2">
            {documents.map((doc) => {
              const selected = selectedDocs.includes(doc.name);
              return (
                <motion.button
                  key={doc.id}
                  onClick={() => toggleDoc(doc.name)}
                  className={`relative flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl transition-all duration-200 ${
                    selected
                      ? "bg-gradient-to-r from-indigo-500/20 to-violet-500/20 border border-indigo-400/30 text-indigo-200 shadow-[0_0_12px_rgba(99,102,241,0.15)]"
                      : "neu-button text-[#94a3b8] hover:text-[#e2e8f0]"
                  }`}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                >
                  {selected && <CheckCircle className="h-3 w-3 text-indigo-400" />}
                  {doc.name}
                </motion.button>
              );
            })}
            {documents.length === 0 && (
              <p className="text-sm text-[#94a3b8]">暂无可用文档</p>
            )}
          </div>

          <input
            type="text"
            placeholder="对比焦点（可选）：如「概念定义」「公式推导」"
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            className="glass-input w-full rounded-xl px-4 py-2.5 text-sm text-[#e2e8f0] placeholder:text-[#94a3b8]/50 outline-none"
          />

          <motion.button
            onClick={handleCompare}
            disabled={isLoading || selectedDocs.length < 2}
            className="neu-button w-full flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium text-[#e2e8f0] disabled:opacity-40 disabled:cursor-not-allowed"
            whileHover={{ scale: selectedDocs.length >= 2 ? 1.01 : 1 }}
            whileTap={{ scale: selectedDocs.length >= 2 ? 0.98 : 1 }}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
            ) : (
              <GitCompare className="h-4 w-4 text-indigo-400" />
            )}
            开始对比
          </motion.button>
        </motion.div>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div
              className="rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400 backdrop-blur-sm"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Results */}
        <AnimatePresence>
          {result && (
            <motion.div
              className="space-y-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {/* Summary */}
              <motion.div
                className="glass-card rounded-2xl p-5"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <h3 className="text-sm font-semibold mb-3 text-[#e2e8f0] flex items-center gap-2">
                  <span>&#128203;</span>
                  对比总结
                </h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap text-[#94a3b8]">{result.summary}</p>
              </motion.div>

              {/* Similarities */}
              {result.similarities && result.similarities.length > 0 && (
                <motion.div
                  className="glass-card rounded-2xl p-5"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                >
                  <h3 className="text-sm font-semibold mb-3 text-[#e2e8f0] flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-emerald-400" />
                    相似之处 ({result.similarities.length})
                  </h3>
                  <motion.ul
                    className="space-y-2"
                    variants={containerVariants}
                    initial="hidden"
                    animate="show"
                  >
                    {result.similarities.map((s, i) => (
                      <motion.li
                        key={i}
                        className="flex items-start gap-2.5 text-sm text-[#94a3b8]"
                        variants={itemVariants}
                      >
                        <span className="shrink-0 mt-0.5 text-[10px] font-bold w-5 h-5 flex items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                          {i + 1}
                        </span>
                        <span>{s}</span>
                      </motion.li>
                    ))}
                  </motion.ul>
                </motion.div>
              )}

              {/* Differences */}
              {result.differences && result.differences.length > 0 && (
                <motion.div
                  className="glass-card rounded-2xl p-5"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                >
                  <h3 className="text-sm font-semibold mb-3 text-[#e2e8f0] flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-orange-400" />
                    不同之处 ({result.differences.length})
                  </h3>
                  <motion.ul
                    className="space-y-2"
                    variants={containerVariants}
                    initial="hidden"
                    animate="show"
                  >
                    {result.differences.map((d, i) => (
                      <motion.li
                        key={i}
                        className="flex items-start gap-2.5 text-sm text-[#94a3b8]"
                        variants={itemVariants}
                      >
                        <span className="shrink-0 mt-0.5 text-[10px] font-bold w-5 h-5 flex items-center justify-center rounded-full bg-orange-500/15 text-orange-400 border border-orange-500/20">
                          {i + 1}
                        </span>
                        <span>{d}</span>
                      </motion.li>
                    ))}
                  </motion.ul>
                </motion.div>
              )}

              {/* Reset */}
              <motion.button
                onClick={() => { setResult(null); setSelectedDocs([]); }}
                className="neu-button w-full rounded-xl py-2.5 text-sm font-medium text-[#94a3b8] hover:text-[#e2e8f0]"
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
              >
                重新对比
              </motion.button>
            </motion.div>
          )}
        </AnimatePresence>

        {!result && !isLoading && !error && (
          <motion.div
            className="flex flex-col items-center justify-center py-16 text-[#94a3b8]"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 }}
          >
            <GitCompare className="h-16 w-16 mb-4 opacity-15" />
            <p className="text-sm">选择至少 2 个文档进行对比</p>
          </motion.div>
        )}
      </div>
    </div>
  );
}
