"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, RefreshCw, Download, ZoomIn, ZoomOut, RotateCcw, Hand, Save, History, Trash2, FileText, Map } from "lucide-react";
import ReactMarkdown from "react-markdown";
import * as api from "@/lib/api";
import type { SavedMindmap, GenerateResponse } from "@/lib/types";

interface MindmapPanelProps {
  sessionId: string | null;
  onNodeClick?: (label: string) => void;
}

export function MindmapPanel({ sessionId, onNodeClick }: MindmapPanelProps) {
  const [mermaidCode, setMermaidCode] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [documents, setDocuments] = useState<{ id: number; name: string }[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [customPrompt, setCustomPrompt] = useState("");
  const [outputType, setOutputType] = useState<"mindmap" | "notes">("mindmap");
  const [notesContent, setNotesContent] = useState("");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDraggingMap, setIsDraggingMap] = useState(false);
  const dragMapRef = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null);
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const onNodeClickRef = useRef(onNodeClick);

  // 保存 & 历史
  const [lastResult, setLastResult] = useState<GenerateResponse | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [savedList, setSavedList] = useState<SavedMindmap[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  useEffect(() => {
    onNodeClickRef.current = onNodeClick;
  }, [onNodeClick]);

  /**
   * 从 SVG 双击事件中提取节点标签。
   * 兼容 Mermaid 10 的 <foreignObject><p> 和传统 <text> 两种渲染方式。
   */
  const extractNodeLabel = useCallback((target: EventTarget | null): string | null => {
    const container = svgContainerRef.current;
    if (!container) return null;

    let el = target as Element | null;
    while (el && el !== container) {
      // 方式 1: <g> 包含 <text>（传统 SVG 文字）
      if (el.tagName.toLowerCase() === "g" && el.querySelector("text")) {
        const textEl = el.querySelector("text");
        if (textEl) {
          const tspans = textEl.querySelectorAll("tspan");
          if (tspans.length > 0) {
            return Array.from(tspans).map(t => t.textContent || "").join(" ").trim();
          }
          return textEl.textContent?.trim() || null;
        }
      }
      // 方式 2: <g> 包含 <foreignObject>（Mermaid 10 htmlLabels）
      if (el.tagName.toLowerCase() === "g" && el.querySelector("foreignObject")) {
        const fo = el.querySelector("foreignObject");
        if (fo) {
          const p = fo.querySelector("p") || fo.querySelector("span") || fo.querySelector("div");
          if (p?.textContent?.trim()) return p.textContent.trim();
          if (fo.textContent?.trim()) return fo.textContent.trim();
        }
      }
      // 方式 3: 直接点击 <p>/<span>（在 foreignObject 内部）
      const tag = el.tagName.toLowerCase();
      if ((tag === "p" || tag === "span" || tag === "div") && el.textContent?.trim()) {
        const parentG = el.closest("g.node") || el.closest("g");
        if (parentG && parentG.querySelector("foreignObject")) {
          return el.textContent.trim();
        }
      }
      el = el.parentElement;
    }
    return null;
  }, []);

  /** 统一的双击处理 */
  const handleDblClick = useCallback((e: MouseEvent | React.MouseEvent) => {
    const label = extractNodeLabel(e.target);
    if (label) {
      e.preventDefault();
      e.stopPropagation();
      onNodeClickRef.current?.(label);
    }
  }, [extractNodeLabel]);

  useEffect(() => {
    api.getDocuments().then((res) => {
      setDocuments(res.documents.filter((d) => d.status === "ready").map((d) => ({ id: d.id, name: d.file_name })));
    }).catch(() => {});
  }, []);

  const handleGenerate = useCallback(async () => {
    if (selectedDocs.length === 0) return;
    setIsLoading(true);
    setError("");
    setNotesContent("");
    setLastResult(null);
    try {
      const res = outputType === "mindmap"
        ? await api.generateMindmap(selectedDocs, customPrompt)
        : await api.generateNotes(selectedDocs, customPrompt);
      if (res.status === "error") {
        setError("生成失败");
      } else if (outputType === "mindmap" && res.mermaid_code) {
        setMermaidCode(res.mermaid_code);
        setZoom(1);
        setPan({ x: 0, y: 0 });
      } else {
        setMermaidCode("");
        setError("");
        setNotesContent(res.content);
      }
      setLastResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [selectedDocs, customPrompt, outputType]);

  // Render mermaid SVG
  useEffect(() => {
    if (!mermaidCode || !svgContainerRef.current) return;
    let cancelled = false;

    (async () => {
      try {
        let cleanCode = mermaidCode.trim();
        if (cleanCode.startsWith("```mermaid")) {
          cleanCode = cleanCode.replace(/^```mermaid\s*\n?/, "").replace(/\n?```\s*$/, "");
        } else if (cleanCode.startsWith("```")) {
          cleanCode = cleanCode.replace(/^```\w*\s*\n?/, "").replace(/\n?```\s*$/, "");
        }

        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: document.documentElement.classList.contains("dark") ? "dark" : "default",
          securityLevel: "loose",
          flowchart: { useMaxWidth: true, htmlLabels: true },
        });

        if (cancelled || !svgContainerRef.current) return;
        svgContainerRef.current.innerHTML = "";
        const id = `mermaid-${Date.now()}`;
        const { svg } = await mermaid.render(id, cleanCode);
        if (cancelled || !svgContainerRef.current) return;
        svgContainerRef.current.innerHTML = svg;

        // Add cursor styles
        const style = document.createElement("style");
        style.textContent = `
          .mindmap-viewport .clickable-node { cursor: pointer !important; }
          .mindmap-viewport .clickable-node:hover { filter: brightness(0.8); }
          .mindmap-viewport .clickable-node { transition: filter 0.15s; }
        `;
        svgContainerRef.current.prepend(style);

        // Mark all <g> with <text> or <foreignObject> as clickable nodes
        const allG = svgContainerRef.current.querySelectorAll("g");
        let nodeCount = 0;
        allG.forEach((g) => {
          if (g.querySelector("text") || g.querySelector("foreignObject")) {
            g.classList.add("clickable-node");
            nodeCount++;
          }
        });
        console.log(`[Mindmap] Rendered ${nodeCount} clickable nodes`);
      } catch (e) {
        if (!cancelled) setError("Mermaid 渲染失败: " + (e as Error).message);
      }
    })();

    return () => { cancelled = true; };
  }, [mermaidCode]);

  // Ctrl + 滚轮缩放，普通滚轮滚动
  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.08 : 0.08;
        setZoom((z) => Math.min(3, Math.max(0.3, z + delta)));
      }
    };
    viewport.addEventListener("wheel", handleWheel, { passive: false });
    return () => viewport.removeEventListener("wheel", handleWheel);
  }, []);

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // 思维导图画布内拖拽
  const handleCanvasMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest("button")) return;
    dragMapRef.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
    setIsDraggingMap(true);
    e.preventDefault();
  }, [pan]);

  const handleCanvasMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragMapRef.current) return;
    const dx = e.clientX - dragMapRef.current.startX;
    const dy = e.clientY - dragMapRef.current.startY;
    setPan({ x: dragMapRef.current.panX + dx, y: dragMapRef.current.panY + dy });
  }, []);

  const handleCanvasMouseUp = useCallback(() => {
    dragMapRef.current = null;
    setIsDraggingMap(false);
  }, []);

  const handleExportSVG = () => {
    if (!svgContainerRef.current) return;
    const svgEl = svgContainerRef.current.querySelector("svg");
    if (!svgEl) return;
    const blob = new Blob([svgEl.outerHTML], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mindmap.svg";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSave = async () => {
    if (!lastResult) return;
    setIsSaving(true);
    try {
      const title = selectedDocs.length > 0
        ? selectedDocs.map(n => n.replace(/\.\w+$/, "")).join(", ")
        : `${outputType === "mindmap" ? "思维导图" : "笔记"} ${new Date().toLocaleString("zh-CN")}`;
      await api.saveMindmap({
        title,
        output_type: lastResult.type,
        content: lastResult.content,
        mermaid_code: lastResult.mermaid_code || undefined,
        file_names: selectedDocs,
      });
      setLastResult(null);
      setHistoryLoaded(false);
    } catch (e) {
      setError("保存失败: " + (e as Error).message);
    } finally {
      setIsSaving(false);
    }
  };

  const loadHistory = async () => {
    try {
      const list = await api.listMindmaps();
      setSavedList(list);
      setHistoryLoaded(true);
    } catch {}
  };

  const toggleHistory = () => {
    if (!showHistory && !historyLoaded) loadHistory();
    setShowHistory(!showHistory);
  };

  const handleLoadSaved = async (item: SavedMindmap) => {
    try {
      const detail = await api.getMindmap(item.id);
      if (detail.output_type === "mindmap" && detail.mermaid_code) {
        setMermaidCode(detail.mermaid_code);
        setNotesContent("");
        setOutputType("mindmap");
      } else {
        setMermaidCode("");
        setNotesContent(detail.content || "");
        setOutputType("notes");
      }
      setZoom(1);
      setPan({ x: 0, y: 0 });
      setError("");
      setLastResult(null);
    } catch (e) {
      setError("加载失败: " + (e as Error).message);
    }
  };

  const handleDeleteSaved = async (id: number) => {
    try {
      await api.deleteMindmap(id);
      setSavedList(prev => prev.filter(m => m.id !== id));
    } catch {}
  };

  const ToolbarButton = ({ onClick, title, children, ...props }: { onClick: () => void; title: string; children: React.ReactNode; [key: string]: unknown }) => (
    <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
      <Button variant="ghost" size="icon" className="h-7 w-7 neu-button border-0 text-[#94a3b8] hover:text-indigo-400" onClick={onClick} title={title} {...props}>
        {children}
      </Button>
    </motion.div>
  );

  return (
    <div className="flex h-full flex-col overflow-y-auto overflow-x-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3 shrink-0">
        <h2 className="text-sm font-semibold text-[#e2e8f0]">🗺️ 思维导图</h2>
        <div className="flex items-center gap-1">
          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 text-[#94a3b8] hover:text-indigo-400" onClick={toggleHistory}>
              <History className="h-3.5 w-3.5" />
              历史
            </Button>
          </motion.div>
          <span className="text-xs text-[#94a3b8] mr-1">{Math.round(zoom * 100)}%</span>
          <ToolbarButton onClick={handleResetView} title="重置视图">
            <RotateCcw className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton onClick={() => setZoom((z) => Math.max(0.3, z - 0.15))} title="缩小">
            <ZoomOut className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton onClick={() => setZoom((z) => Math.min(3, z + 0.15))} title="放大">
            <ZoomIn className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton onClick={handleExportSVG} title="导出 SVG">
            <Download className="h-3.5 w-3.5" />
          </ToolbarButton>
          <ToolbarButton
            onClick={() => {
              console.log("[Mindmap] Test button clicked");
              if (onNodeClickRef.current) {
                onNodeClickRef.current("测试节点");
              }
            }}
            title="测试双击"
          >
            🧪
          </ToolbarButton>
        </div>
      </div>

      {/* Controls */}
      <div className="space-y-2 border-b border-white/[0.06] p-4 shrink-0">
        <div className="flex gap-2">
          <Select value={outputType} onValueChange={(v) => v && setOutputType(v as "mindmap" | "notes")}>
            <SelectTrigger className="h-8 text-xs glass-input border-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="mindmap">思维导图</SelectItem>
              <SelectItem value="notes">重点笔记</SelectItem>
            </SelectContent>
          </Select>
        </div>

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
                {doc.name.length > 15 ? doc.name.slice(0, 15) + "..." : doc.name}
              </Button>
            </motion.div>
          ))}
          {documents.length === 0 && (
            <p className="text-xs text-[#94a3b8]">暂无可用文档</p>
          )}
        </div>

        <Input
          placeholder="自定义提示词（可选）"
          value={customPrompt}
          onChange={(e) => setCustomPrompt(e.target.value)}
          className="h-8 text-xs glass-input border-0"
        />

        <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
          <Button
            onClick={handleGenerate}
            disabled={isLoading || selectedDocs.length === 0}
            className="w-full h-8 text-xs relative overflow-hidden group bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 border-0 shadow-lg shadow-indigo-500/20"
            size="sm"
          >
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <RefreshCw className="h-3.5 w-3.5 mr-1" />}
            生成
          </Button>
        </motion.div>
      </div>

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
              <p className="text-[10px] font-medium text-[#94a3b8]">已保存的记录</p>
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
                      {item.output_type === "mindmap" ? (
                        <Map className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                      ) : (
                        <FileText className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                      )}
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
        {lastResult && (
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
                保存此{lastResult.type === "mindmap" ? "思维导图" : "笔记"}
              </Button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Viewport — 画布区域 */}
      <div
        ref={viewportRef}
        className="mindmap-viewport relative flex-1"
        onDoubleClick={handleDblClick}
      >
        {error && (
          <motion.div
            className="m-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-400"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {error}
          </motion.div>
        )}

        {/* 笔记模式 */}
        {notesContent && !mermaidCode && !error && (
          <motion.div
            className="p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <div className="prose prose-sm dark:prose-invert max-w-none glass-card rounded-xl p-4">
              <ReactMarkdown>{notesContent}</ReactMarkdown>
            </div>
          </motion.div>
        )}

        {/* 思维导图 — 固定高度画布，内部拖拽移动 */}
        {mermaidCode && !error && (
          <div
            ref={canvasRef}
            className={`mindmap-canvas relative w-full overflow-hidden ${isDraggingMap ? "cursor-grabbing" : "cursor-grab"}`}
            style={{ height: "calc(100vh - 320px)", minHeight: "300px" }}
            onMouseDown={handleCanvasMouseDown}
            onMouseMove={handleCanvasMouseMove}
            onMouseUp={handleCanvasMouseUp}
            onMouseLeave={handleCanvasMouseUp}
          >
            <div
              className="py-8 px-[10%] transition-transform duration-75"
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transformOrigin: "top center",
              }}
            >
              <div ref={svgContainerRef} className="inline-block w-full" />
            </div>

            {/* 提示 */}
            <div className="absolute bottom-3 right-3 flex items-center gap-1 rounded-lg glass-card px-2 py-1 text-[10px] text-[#94a3b8]">
              拖拽移动 · Ctrl+滚轮缩放 · 双击节点
            </div>
          </div>
        )}

        {/* 空状态 */}
        {!mermaidCode && !notesContent && !error && !isLoading && (
          <motion.div
            className="flex flex-col items-center justify-center h-full"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
          >
            <Hand className="h-8 w-8 mb-2 text-[#94a3b8]/30" />
            <p className="text-sm text-[#94a3b8]">选择文档后点击生成</p>
            <p className="text-xs mt-1 text-[#94a3b8]/60">Ctrl+滚轮缩放 · 拖拽移动 · 双击节点查看解释</p>
          </motion.div>
        )}
      </div>

    </div>
  );
}
