"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, RefreshCw, CheckCircle, XCircle, ChevronRight, Save, History, Trash2, FileText } from "lucide-react";
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
        setQuestions(res.questions);
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
      setQuestions(detail.questions);
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

  const currentQuestion = questions[currentIndex];

  return (
    <div className="flex h-full flex-col overflow-y-auto overflow-x-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3 shrink-0">
        <h2 className="text-sm font-semibold">📝 测验</h2>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={toggleHistory}>
            <History className="h-3.5 w-3.5" />
            历史
          </Button>
          {score.total > 0 && (
            <Badge variant="outline">
              {score.correct}/{score.total} 正确
            </Badge>
          )}
        </div>
      </div>

      {/* Setup */}
      {questions.length === 0 && (
        <div className="space-y-3 border-b p-4 shrink-0">
          <div className="flex flex-wrap gap-1">
            {documents.map((doc) => (
              <Button
                key={doc.id}
                variant={selectedDocs.includes(doc.name) ? "default" : "outline"}
                size="sm"
                className="h-7 text-xs"
                onClick={() =>
                  setSelectedDocs((prev) =>
                    prev.includes(doc.name) ? prev.filter((d) => d !== doc.name) : [...prev, doc.name]
                  )
                }
              >
                {doc.name.length > 12 ? doc.name.slice(0, 12) + "..." : doc.name}
              </Button>
            ))}
          </div>
          <div className="flex gap-2">
            <Select value={String(numQuestions)} onValueChange={(v) => v && setNumQuestions(Number(v))}>
              <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[3, 5, 10, 15].map((n) => <SelectItem key={n} value={String(n)}>{n} 题</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={difficulty} onValueChange={(v) => v && setDifficulty(v)}>
              <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="easy">简单</SelectItem>
                <SelectItem value="medium">中等</SelectItem>
                <SelectItem value="hard">困难</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button onClick={handleGenerate} disabled={isLoading || selectedDocs.length === 0} className="w-full h-8 text-xs">
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <RefreshCw className="h-3.5 w-3.5 mr-1" />}
            生成测验
          </Button>
        </div>
      )}

      {/* History list */}
      {showHistory && (
        <div className="border-b shrink-0">
          <div className="flex items-center justify-between px-4 py-1.5 border-b bg-muted/30">
            <p className="text-[10px] font-medium text-muted-foreground">已保存的测验</p>
            <span className="text-[10px] text-muted-foreground">{savedList.length} 条</span>
          </div>
          <div className="overflow-y-auto" style={{ height: "140px" }}>
            {savedList.length === 0 ? (
              <p className="px-4 py-3 text-xs text-muted-foreground">暂无保存的记录</p>
            ) : (
              <div className="divide-y">
                {savedList.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-2 px-4 py-2 hover:bg-accent/50 cursor-pointer group"
                    onClick={() => handleLoadSaved(item)}
                  >
                    <FileText className="h-3.5 w-3.5 text-primary shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{item.title}</p>
                      <p className="text-[10px] text-muted-foreground">
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
                      <Trash2 className="h-3 w-3 text-muted-foreground hover:text-red-500" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Save button */}
      {questions.length > 0 && score.total > 0 && (
        <div className="border-b px-4 py-2 shrink-0">
          <Button
            onClick={handleSave}
            disabled={isSaving}
            variant="outline"
            size="sm"
            className="w-full h-8 text-xs"
          >
            {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Save className="h-3.5 w-3.5 mr-1" />}
            保存此测验
          </Button>
        </div>
      )}

      {/* Question display */}
      <div className="flex-1 p-4 overflow-y-auto">
        {currentQuestion && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge variant="outline">{currentIndex + 1}/{questions.length}</Badge>
              <Badge variant="secondary">{currentQuestion.type === "choice" ? "选择题" : currentQuestion.type === "fill" ? "填空题" : "简答题"}</Badge>
              {currentQuestion.topic && <Badge variant="outline">{currentQuestion.topic}</Badge>}
            </div>

            <p className="text-sm font-medium">{currentQuestion.question}</p>

            {/* Options for choice questions */}
            {currentQuestion.type === "choice" && currentQuestion.options && (
              <div className="space-y-1.5">
                {currentQuestion.options.map((opt, i) => (
                  <Button
                    key={i}
                    variant={userAnswer === opt ? "default" : "outline"}
                    className="w-full justify-start h-auto py-2 text-xs whitespace-normal"
                    onClick={() => setUserAnswer(opt)}
                  >
                    {opt}
                  </Button>
                ))}
              </div>
            )}

            {/* Input for non-choice questions */}
            {currentQuestion.type !== "choice" && (
              <Input
                placeholder="输入你的答案..."
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                className="text-xs"
                onKeyDown={(e) => e.key === "Enter" && !result && handleCheck()}
              />
            )}

            {/* Check button */}
            {!result && (
              <Button onClick={handleCheck} disabled={!userAnswer.trim()} className="w-full h-8 text-xs">
                提交答案
              </Button>
            )}

            {/* Result */}
            {result && (
              <div className={`rounded-xl border p-3 text-sm ${result.correct ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950" : "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950"}`}>
                <div className="flex items-center gap-2 font-medium">
                  {result.correct ? (
                    <><CheckCircle className="h-4 w-4 text-green-500" /> 正确！</>
                  ) : (
                    <><XCircle className="h-4 w-4 text-red-500" /> 错误</>
                  )}
                </div>
                {currentQuestion.answer && !result.correct && (
                  <p className="mt-1 text-xs text-muted-foreground">正确答案: {currentQuestion.answer}</p>
                )}
                {result.explanation && (
                  <p className="mt-2 text-xs text-muted-foreground">{result.explanation}</p>
                )}
              </div>
            )}

            {/* Next button */}
            {result && currentIndex < questions.length - 1 && (
              <Button onClick={handleNext} variant="outline" className="w-full h-8 text-xs">
                下一题 <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            )}

            {/* Final score */}
            {result && currentIndex === questions.length - 1 && score.total > 0 && (
              <div className="rounded-xl border bg-card p-4 text-center">
                <p className="text-lg font-semibold">测验完成！</p>
                <p className="text-sm text-muted-foreground mt-1">
                  正确率: {score.correct}/{score.total} ({Math.round((score.correct / score.total) * 100)}%)
                </p>
                <Button onClick={() => { setQuestions([]); setScore({ correct: 0, total: 0 }); }} variant="outline" className="mt-3 h-8 text-xs">
                  重新开始
                </Button>
              </div>
            )}
          </div>
        )}

        {questions.length === 0 && !isLoading && (
          <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
            <p className="text-sm">选择文档后生成测验</p>
          </div>
        )}
      </div>
    </div>
  );
}
