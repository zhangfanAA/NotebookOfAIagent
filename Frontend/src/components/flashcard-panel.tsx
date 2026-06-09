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
        setCards(res.flashcards);
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
      setCards(detail.cards);
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

  const currentCard = cards[currentIndex];

  return (
    <div className="flex h-full flex-col overflow-y-auto overflow-x-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3 shrink-0">
        <h2 className="text-sm font-semibold">🃏 闪卡</h2>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={toggleHistory}>
            <History className="h-3.5 w-3.5" />
            历史
          </Button>
          {cards.length > 0 && (
            <Badge variant="outline">{currentIndex + 1}/{cards.length}</Badge>
          )}
        </div>
      </div>

      {/* Setup */}
      {cards.length === 0 && (
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
            <Select value={String(numCards)} onValueChange={(v) => v && setNumCards(Number(v))}>
              <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[5, 10, 15, 20].map((n) => <SelectItem key={n} value={String(n)}>{n} 张</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Input
            placeholder="主题聚焦（可选）"
            value={topicFocus}
            onChange={(e) => setTopicFocus(e.target.value)}
            className="h-8 text-xs"
          />
          <Button onClick={handleGenerate} disabled={isLoading || selectedDocs.length === 0} className="w-full h-8 text-xs">
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <RefreshCw className="h-3.5 w-3.5 mr-1" />}
            生成闪卡
          </Button>
        </div>
      )}

      {/* History list */}
      {showHistory && (
        <div className="border-b shrink-0">
          <div className="flex items-center justify-between px-4 py-1.5 border-b bg-muted/30">
            <p className="text-[10px] font-medium text-muted-foreground">已保存的闪卡集</p>
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
      {cards.length > 0 && (
        <div className="border-b px-4 py-2 shrink-0">
          <Button
            onClick={handleSave}
            disabled={isSaving}
            variant="outline"
            size="sm"
            className="w-full h-8 text-xs"
          >
            {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Save className="h-3.5 w-3.5 mr-1" />}
            保存此闪卡集
          </Button>
        </div>
      )}

      {/* Card display */}
      <div className="flex-1 p-4 overflow-y-auto">
        {currentCard && (
          <div className="space-y-4">
            {/* Card */}
            <div
              className="cursor-pointer perspective-1000"
              onClick={() => setIsFlipped(!isFlipped)}
            >
              <AnimatePresence mode="wait">
                <motion.div
                  key={isFlipped ? "back" : "front"}
                  initial={{ rotateY: 90, opacity: 0 }}
                  animate={{ rotateY: 0, opacity: 1 }}
                  exit={{ rotateY: -90, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`rounded-2xl border p-6 min-h-[200px] flex flex-col items-center justify-center text-center shadow-sm ${
                    isFlipped
                      ? "bg-primary/5 border-primary/20"
                      : "bg-card"
                  }`}
                >
                  <Badge variant="outline" className="mb-3 text-[10px]">
                    {isFlipped ? "答案" : "问题"}
                  </Badge>
                  <p className="text-sm leading-relaxed">
                    {isFlipped ? currentCard.back : currentCard.front}
                  </p>
                  {currentCard.topic && (
                    <Badge variant="secondary" className="mt-3 text-[10px]">
                      {currentCard.topic}
                    </Badge>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>

            <p className="text-center text-xs text-muted-foreground">
              点击卡片 {isFlipped ? "查看问题" : "查看答案"}
            </p>

            {/* Navigation */}
            <div className="flex items-center justify-center gap-2">
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={handlePrev} disabled={currentIndex === 0}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setIsFlipped(!isFlipped)}>
                <RotateCcw className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={handleNext} disabled={currentIndex === cards.length - 1}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            {/* Progress dots */}
            <div className="flex justify-center gap-1">
              {cards.map((_, i) => (
                <button
                  key={i}
                  className={`h-1.5 rounded-full transition-all ${
                    i === currentIndex ? "w-6 bg-primary" : "w-1.5 bg-muted-foreground/30"
                  }`}
                  onClick={() => { setCurrentIndex(i); setIsFlipped(false); }}
                />
              ))}
            </div>

            {/* Reset */}
            <Button onClick={() => { setCards([]); setCurrentIndex(0); setIsFlipped(false); }} variant="outline" className="w-full h-8 text-xs">
              重新生成
            </Button>
          </div>
        )}

        {cards.length === 0 && !isLoading && (
          <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
            <p className="text-sm">选择文档后生成闪卡</p>
          </div>
        )}
      </div>
    </div>
  );
}
