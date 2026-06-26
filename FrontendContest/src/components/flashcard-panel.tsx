"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, RefreshCw, ChevronLeft, ChevronRight, RotateCcw, Save, History, Trash2, FileText } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { Flashcard, SavedFlashcardSet } from "@/lib/types";
import * as api from "@/lib/api";

export function FlashcardPanel() {
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [documents, setDocuments] = useState<{ id: number; name: string }[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [numCards, setNumCards] = useState(10);
  const [topicFocus, setTopicFocus] = useState("");

  // 保存 & 历史
  const [isSaving, setIsSaving] = useState(false);
  const [savedList, setSavedList] = useState<SavedFlashcardSet[]>([]);
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
      const res = await api.generateFlashcards(selectedDocs, numCards, topicFocus);
      if (res.status === "success") {
        setCards(res.flashcards || []);
        setCurrentIndex(0);
        setIsFlipped(false);
      }
    } catch (e) {
      console.error("Flashcard generation failed:", e);
    } finally {
      setIsLoading(false);
    }
  }, [selectedDocs, numCards, topicFocus]);

  const handlePrev = () => {
    setCurrentIndex((i) => Math.max(0, i - 1));
    setIsFlipped(false);
  };

  const handleNext = () => {
    setCurrentIndex((i) => Math.min(cards.length - 1, i + 1));
    setIsFlipped(false);
  };

  const handleSave = async () => {
    if (cards.length === 0) return;
    setIsSaving(true);
    try {
      const title = selectedDocs.length > 0
        ? selectedDocs.map(n => n.replace(/\.\w+$/, "")).join(", ")
        : `闪卡 ${new Date().toLocaleString("zh-CN")}`;
      await api.saveFlashcardSet({
        title,
        cards,
        file_names: selectedDocs,
      });
      setHistoryLoaded(false);
    } catch (e) {
      console.error("Save flashcards failed:", e);
    } finally {
      setIsSaving(false);
    }
  };

  const loadHistory = async () => {
    try {
      const list = await api.listFlashcardSets();
      setSavedList(list);
      setHistoryLoaded(true);
    } catch {}
  };

  const toggleHistory = () => {
    if (!showHistory && !historyLoaded) loadHistory();
    setShowHistory(!showHistory);
  };

  const handleLoadSaved = async (item: SavedFlashcardSet) => {
    try {
      const detail = await api.getFlashcardSet(item.id);
      setCards(detail.cards || []);
      setCurrentIndex(0);
      setIsFlipped(false);
    } catch (e) {
      console.error("Load flashcards failed:", e);
    }
  };

  const handleDeleteSaved = async (id: number) => {
    try {
      await api.deleteFlashcardSet(id);
      setSavedList(prev => prev.filter(f => f.id !== id));
    } catch {}
  };

  const currentCard = cards?.[currentIndex];

  return (
    <div className="flex h-full flex-col overflow-y-auto overflow-x-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3 shrink-0">
        <h2 className="text-sm font-semibold text-[#e2e8f0]">🃏 闪卡</h2>
        <div className="flex items-center gap-2">
          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 text-[#94a3b8] hover:text-indigo-400" onClick={toggleHistory}>
              <History className="h-3.5 w-3.5" />
              历史
            </Button>
          </motion.div>
          <AnimatePresence>
            {cards.length > 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
              >
                <Badge variant="outline" className="border-indigo-500/30 text-indigo-300 bg-indigo-500/10">{currentIndex + 1}/{cards.length}</Badge>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Setup */}
      <AnimatePresence>
        {cards.length === 0 && (
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
              <Select value={String(numCards)} onValueChange={(v) => v && setNumCards(Number(v))}>
                <SelectTrigger className="h-8 text-xs glass-input border-0"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[5, 10, 15, 20].map((n) => <SelectItem key={n} value={String(n)}>{n} 张</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Input
              placeholder="主题聚焦（可选）"
              value={topicFocus}
              onChange={(e) => setTopicFocus(e.target.value)}
              className="h-8 text-xs glass-input border-0"
            />
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button onClick={handleGenerate} disabled={isLoading || selectedDocs.length === 0} className="w-full h-8 text-xs bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 border-0 shadow-lg shadow-indigo-500/20">
                {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <RefreshCw className="h-3.5 w-3.5 mr-1" />}
                生成闪卡
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
              <p className="text-[10px] font-medium text-[#94a3b8]">已保存的闪卡集</p>
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
                          {item.file_names?.join(", ") || ""}
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
        {cards.length > 0 && (
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
                保存此闪卡集
              </Button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Card display */}
      <div className="flex-1 p-4 overflow-y-auto">
        <AnimatePresence mode="wait">
          {currentCard && (
            <motion.div
              key={currentIndex}
              className="space-y-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {/* Card with 3D flip */}
              <div
                className="cursor-pointer"
                style={{ perspective: "1000px" }}
                onClick={() => setIsFlipped(!isFlipped)}
              >
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={isFlipped ? "back" : "front"}
                    initial={{ rotateY: 90, opacity: 0 }}
                    animate={{ rotateY: 0, opacity: 1 }}
                    exit={{ rotateY: -90, opacity: 0 }}
                    transition={{ duration: 0.35, ease: "easeInOut" as const }}
                    className={`rounded-2xl p-6 min-h-[200px] flex flex-col items-center justify-center text-center ${
                      isFlipped
                        ? "glass-card border border-indigo-500/20 shadow-[0_0_30px_rgba(99,102,241,0.08)]"
                        : "glass-card"
                    }`}
                    style={{ transformStyle: "preserve-3d" }}
                  >
                    <Badge
                      variant="outline"
                      className={`mb-3 text-[10px] border-0 ${
                        isFlipped
                          ? "bg-indigo-500/15 text-indigo-300"
                          : "bg-white/[0.06] text-[#94a3b8]"
                      }`}
                    >
                      {isFlipped ? "答案" : "问题"}
                    </Badge>
                    <p className="text-sm leading-relaxed text-[#e2e8f0]">
                      {isFlipped ? currentCard.back : currentCard.front}
                    </p>
                    {currentCard.topic && (
                      <Badge variant="secondary" className="mt-3 text-[10px] bg-purple-500/15 text-purple-300 border-0">
                        {currentCard.topic}
                      </Badge>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>

              <p className="text-center text-xs text-[#94a3b8]">
                点击卡片 {isFlipped ? "查看问题" : "查看答案"}
              </p>

              {/* Navigation */}
              <div className="flex items-center justify-center gap-2">
                <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                  <Button variant="outline" size="icon" className="h-8 w-8 neu-button border-0 text-[#94a3b8] hover:text-indigo-400" onClick={handlePrev} disabled={currentIndex === 0}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                  <Button variant="outline" size="icon" className="h-8 w-8 neu-button border-0 text-[#94a3b8] hover:text-indigo-400" onClick={() => setIsFlipped(!isFlipped)}>
                    <RotateCcw className="h-4 w-4" />
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                  <Button variant="outline" size="icon" className="h-8 w-8 neu-button border-0 text-[#94a3b8] hover:text-indigo-400" onClick={handleNext} disabled={currentIndex === cards.length - 1}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </motion.div>
              </div>

              {/* Progress bar */}
              <div className="flex justify-center">
                <div className="w-full max-w-[200px] h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${((currentIndex + 1) / cards.length) * 100}%` }}
                    transition={{ duration: 0.3, ease: "easeOut" as const }}
                  />
                </div>
              </div>

              {/* Progress dots */}
              <div className="flex justify-center gap-1 flex-wrap max-w-full">
                {cards.map((_, i) => (
                  <motion.button
                    key={i}
                    className={`h-1.5 rounded-full transition-all ${
                      i === currentIndex
                        ? "w-6 bg-gradient-to-r from-indigo-500 to-purple-500"
                        : i < currentIndex
                        ? "w-1.5 bg-indigo-500/40"
                        : "w-1.5 bg-white/[0.1]"
                    }`}
                    onClick={() => { setCurrentIndex(i); setIsFlipped(false); }}
                    whileHover={{ scale: 1.3 }}
                  />
                ))}
              </div>

              {/* Reset */}
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                <Button onClick={() => { setCards([]); setCurrentIndex(0); setIsFlipped(false); }} variant="outline" className="w-full h-8 text-xs neu-button border-0 text-[#94a3b8]">
                  重新生成
                </Button>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {cards.length === 0 && !isLoading && (
            <motion.div
              className="flex h-full flex-col items-center justify-center"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
            >
              <p className="text-sm text-[#94a3b8]">选择文档后生成闪卡</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
