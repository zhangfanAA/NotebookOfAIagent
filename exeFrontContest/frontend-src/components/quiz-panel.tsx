"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, RefreshCw, CheckCircle, XCircle, ChevronRight, ChevronLeft, Save, History, Trash2, FileText } from "lucide-react";
import type { QuizQuestion, SavedQuiz } from "@/lib/types";
import * as api from "@/lib/api";

export function QuizPanel() {
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userAnswer, setUserAnswer] = useState("");
  const [result, setResult] = useState<{ correct: boolean; explanation: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [documents, setDocuments] = useState<{ id: number; name: string }[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [numQuestions, setNumQuestions] = useState(5);
  const [difficulty, setDifficulty] = useState("medium");
  const [score, setScore] = useState({ correct: 0, total: 0 });

  // 保存 & 历史
  const [isSaving, setIsSaving] = useState(false);
  const [savedList, setSavedList] = useState<SavedQuiz[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  useEffect(() => {
    api.getDocuments().then((res) => {
      setDocuments(res.documents.filter((d) => d.status === "ready").map((d) => ({ id: d.id, name: d.file_name })));
    }).catch(() => {});
  }, []);

  const handleGenerate = useCallback(async () => {
    if (selectedDocs.length === 0) return;
    setIsLoading(true);
    try {
      const res = await api.generateQuiz(selectedDocs, numQuestions, difficulty);
      if (res.status === "success") {
        setQuestions(res.questions || []);
        setCurrentIndex(0);
        setUserAnswer("");
        setResult(null);
        setScore({ correct: 0, total: 0 });
      }
    } catch (e) {
      console.error("Quiz generation failed:", e);
    } finally {
      setIsLoading(false);
    }
  }, [selectedDocs, numQuestions, difficulty]);

  const handleCheck = useCallback(async () => {
    if (!questions[currentIndex] || !userAnswer.trim()) return;
    try {
      const res = await api.checkQuizAnswer(questions[currentIndex], userAnswer);
      setResult(res);
      setScore((prev) => ({
        correct: prev.correct + (res.correct ? 1 : 0),
        total: prev.total + 1,
      }));
    } catch (e) {
      console.error("Check failed:", e);
    }
  }, [questions, currentIndex, userAnswer]);

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((i) => i + 1);
      setUserAnswer("");
      setResult(null);
    }
  };

  const handleSave = async () => {
    if (questions.length === 0) return;
    setIsSaving(true);
    try {
      const title = selectedDocs.length > 0
        ? selectedDocs.map(n => n.replace(/\.\w+$/, "")).join(", ")
        : `测验 ${new Date().toLocaleString("zh-CN")}`;
      await api.saveQuiz({
        title,
        questions,
        score_correct: score.correct,
        score_total: score.total,
        difficulty,
        file_names: selectedDocs,
      });
      setHistoryLoaded(false);
    } catch (e) {
      console.error("Save quiz failed:", e);
    } finally {
      setIsSaving(false);
    }
  };

  const loadHistory = async () => {
    try {
      const list = await api.listQuizzes();
      setSavedList(list);
      setHistoryLoaded(true);
    } catch {}
  };

  const toggleHistory = () => {
    if (!showHistory && !historyLoaded) loadHistory();
    setShowHistory(!showHistory);
  };

  const handleLoadSaved = async (item: SavedQuiz) => {
    try {
      const detail = await api.getQuiz(item.id);
      setQuestions(detail.questions || []);
      setCurrentIndex(0);
      setUserAnswer("");
      setResult(null);
      setScore({ correct: detail.score_correct, total: detail.score_total });
      setDifficulty(detail.difficulty || "medium");
    } catch (e) {
      console.error("Load quiz failed:", e);
    }
  };

  const handleDeleteSaved = async (id: number) => {
    try {
      await api.deleteQuiz(id);
      setSavedList(prev => prev.filter(q => q.id !== id));
    } catch {}
  };

  const currentQuestion = questions?.[currentIndex];

  return (
    <div className="flex h-full flex-col overflow-y-auto overflow-x-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3 shrink-0">
        <h2 className="text-sm font-semibold text-[#e2e8f0]">📝 测验</h2>
        <div className="flex items-center gap-2">
          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 text-[#94a3b8] hover:text-indigo-400" onClick={toggleHistory}>
              <History className="h-3.5 w-3.5" />
              历史
            </Button>
          </motion.div>
          <AnimatePresence>
            {score.total > 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
              >
                <Badge variant="outline" className="border-indigo-500/30 text-indigo-300 bg-indigo-500/10">
                  {score.correct}/{score.total} 正确
                </Badge>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Setup */}
      <AnimatePresence>
        {questions.length === 0 && (
          <motion.div
            className="space-y-3 border-b border-white/[0.06] p-4 shrink-0"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <div className="flex flex-wrap gap-1">
              {documents.map((doc) => (
                <motion.div key={doc.id} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    variant={selectedDocs.includes(doc.name) ? "default" : "outline"}
                    size="sm"
                    className={`h-7 text-xs ${
                      selectedDocs.includes(doc.name)
                        ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                        : "neu-button border-0 text-[#94a3b8]"
                    }`}
                    onClick={() =>
                      setSelectedDocs((prev) =>
                        prev.includes(doc.name) ? prev.filter((d) => d !== doc.name) : [...prev, doc.name]
                      )
                    }
                  >
                    {doc.name.length > 12 ? doc.name.slice(0, 12) + "..." : doc.name}
                  </Button>
                </motion.div>
              ))}
            </div>
            <div className="flex gap-2">
              <Select value={String(numQuestions)} onValueChange={(v) => v && setNumQuestions(Number(v))}>
                <SelectTrigger className="h-8 text-xs glass-input border-0"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[3, 5, 10, 15].map((n) => <SelectItem key={n} value={String(n)}>{n} 题</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={difficulty} onValueChange={(v) => v && setDifficulty(v)}>
                <SelectTrigger className="h-8 text-xs glass-input border-0"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="easy">简单</SelectItem>
                  <SelectItem value="medium">中等</SelectItem>
                  <SelectItem value="hard">困难</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button onClick={handleGenerate} disabled={isLoading || selectedDocs.length === 0} className="w-full h-8 text-xs bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 border-0 shadow-lg shadow-indigo-500/20">
                {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <RefreshCw className="h-3.5 w-3.5 mr-1" />}
                生成测验
              </Button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* History list */}
      <AnimatePresence>
        {showHistory && (
          <motion.div
            className="border-b border-white/[0.06] shrink-0"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="flex items-center justify-between px-4 py-1.5 border-b border-white/[0.06] bg-white/[0.02]">
              <p className="text-[10px] font-medium text-[#94a3b8]">已保存的测验</p>
              <span className="text-[10px] text-[#94a3b8]">{savedList.length} 条</span>
            </div>
            <div className="overflow-y-auto" style={{ height: "140px" }}>
              {savedList.length === 0 ? (
                <p className="px-4 py-3 text-xs text-[#94a3b8]">暂无保存的记录</p>
              ) : (
                <div className="divide-y divide-white/[0.06]">
                  {savedList.map((item, i) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.03 }}
                      className="flex items-center gap-2 px-4 py-2 hover:bg-white/[0.03] cursor-pointer group"
                      onClick={() => handleLoadSaved(item)}
                    >
                      <FileText className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate text-[#e2e8f0]">{item.title}</p>
                        <p className="text-[10px] text-[#94a3b8]">
                          {item.score_correct}/{item.score_total} 正确 · {item.difficulty}
                          {item.created_at ? ` · ${new Date(item.created_at).toLocaleDateString("zh-CN")}` : ""}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => { e.stopPropagation(); handleDeleteSaved(item.id); }}
                      >
                        <Trash2 className="h-3 w-3 text-[#94a3b8] hover:text-red-400" />
                      </Button>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Save button */}
      <AnimatePresence>
        {questions.length > 0 && score.total > 0 && (
          <motion.div
            className="border-b border-white/[0.06] px-4 py-2 shrink-0"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                onClick={handleSave}
                disabled={isSaving}
                variant="outline"
                size="sm"
                className="w-full h-8 text-xs neu-button border-0 text-[#94a3b8]"
              >
                {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Save className="h-3.5 w-3.5 mr-1" />}
                保存此测验
              </Button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Question display */}
      <div className="flex-1 p-4 overflow-y-auto">
        <AnimatePresence mode="wait">
          {currentQuestion && (
            <motion.div
              key={currentIndex}
              className="space-y-4"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
            >
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-indigo-500/30 text-indigo-300 bg-indigo-500/10">{currentIndex + 1}/{questions.length}</Badge>
                <Badge variant="secondary" className="bg-white/[0.06] text-[#94a3b8]">{currentQuestion.type === "choice" ? "选择题" : currentQuestion.type === "fill" ? "填空题" : "简答题"}</Badge>
                {currentQuestion.topic && <Badge variant="outline" className="border-purple-500/30 text-purple-300 bg-purple-500/10">{currentQuestion.topic}</Badge>}
              </div>

              <p className="text-sm font-medium text-[#e2e8f0]">{currentQuestion.question}</p>

              {/* Options for choice questions */}
              {currentQuestion.type === "choice" && currentQuestion.options && (
                <div className="space-y-1.5">
                  {currentQuestion.options.map((opt, i) => {
                    const letter = opt.match(/^([A-Da-d])/)?.[1]?.toUpperCase() || opt;
                    const isSelected = userAnswer === letter;
                    return (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.05 }}
                        whileHover={{ scale: 1.02, x: 4 }}
                        whileTap={{ scale: 0.98 }}
                      >
                        <Button
                          variant="outline"
                          className={`w-full justify-start h-auto py-2 text-xs whitespace-normal transition-all ${
                            isSelected
                              ? "bg-indigo-500/20 border-indigo-500/40 text-indigo-300 shadow-[0_0_12px_rgba(99,102,241,0.15)]"
                              : "glass-card border-0 text-[#94a3b8] hover:text-[#e2e8f0]"
                          }`}
                          onClick={() => setUserAnswer(letter)}
                        >
                          {opt}
                        </Button>
                      </motion.div>
                    );
                  })}
                </div>
              )}

              {/* Input for non-choice questions */}
              {currentQuestion.type !== "choice" && (
                <Input
                  placeholder="输入你的答案..."
                  value={userAnswer}
                  onChange={(e) => setUserAnswer(e.target.value)}
                  className="text-xs glass-input border-0"
                  onKeyDown={(e) => e.key === "Enter" && !result && handleCheck()}
                />
              )}

              {/* Check button */}
              <AnimatePresence>
                {!result && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <Button onClick={handleCheck} disabled={!userAnswer.trim()} className="w-full h-8 text-xs bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 border-0 shadow-lg shadow-indigo-500/20">
                      提交答案
                    </Button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Result */}
              <AnimatePresence>
                {result && (
                  <motion.div
                    className={`rounded-xl p-3 text-sm glass-card ${
                      result.correct
                        ? "border border-emerald-500/30 shadow-[0_0_20px_rgba(52,211,153,0.1)]"
                        : "border border-red-500/30 shadow-[0_0_20px_rgba(248,113,113,0.1)]"
                    }`}
                    initial={{ opacity: 0, scale: 0.95, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ type: "spring", stiffness: 300, damping: 25 }}
                  >
                    <div className="flex items-center gap-2 font-medium">
                      {result.correct ? (
                        <><CheckCircle className="h-4 w-4 text-emerald-400" /> <span className="text-emerald-400">正确！</span></>
                      ) : (
                        <><XCircle className="h-4 w-4 text-red-400" /> <span className="text-red-400">错误</span></>
                      )}
                    </div>
                    {currentQuestion.answer && !result.correct && (
                      <p className="mt-1 text-xs text-[#94a3b8]">正确答案: {currentQuestion.answer}</p>
                    )}
                    {result.explanation && (
                      <p className="mt-2 text-xs text-[#94a3b8]">{result.explanation}</p>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Next button */}
              <AnimatePresence>
                {result && currentIndex < questions.length - 1 && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <Button onClick={handleNext} variant="outline" className="w-full h-8 text-xs neu-button border-0 text-[#94a3b8]">
                      下一题 <ChevronRight className="h-3.5 w-3.5 ml-1" />
                    </Button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Final score */}
              <AnimatePresence>
                {result && currentIndex === questions.length - 1 && score.total > 0 && (
                  <motion.div
                    className="rounded-xl glass-card p-4 text-center"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: "spring", stiffness: 300, damping: 25 }}
                  >
                    <p className="text-lg font-semibold text-glow text-[#e2e8f0]">测验完成！</p>
                    <motion.p
                      className="text-sm text-[#94a3b8] mt-1"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.3 }}
                    >
                      正确率: {score.correct}/{score.total} ({Math.round((score.correct / score.total) * 100)}%)
                    </motion.p>
                    <motion.div
                      className="mt-3"
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <Button onClick={() => { setQuestions([]); setScore({ correct: 0, total: 0 }); }} variant="outline" className="h-8 text-xs neu-button border-0 text-[#94a3b8]">
                        重新开始
                      </Button>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {questions.length === 0 && !isLoading && (
            <motion.div
              className="flex h-full flex-col items-center justify-center"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
            >
              <p className="text-sm text-[#94a3b8]">选择文档后生成测验</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
