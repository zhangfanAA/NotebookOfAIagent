"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Sun, Moon, Plus, Search, Trash2, Pencil, Check, X,
  Map, FileQuestion, Layers, BarChart3, GitCompare,
  Upload, Database, ChevronDown, ChevronRight,
  Download, Settings, LogOut,
  Shield, Wallet, Bell,
} from "lucide-react";
import type { PanelType, Session, Message, Document } from "@/lib/types";
import * as api from "@/lib/api";
import { removeToken, useAuth } from "@/lib/auth";

interface SidebarProps {
  darkMode: boolean;
  onToggleDark: () => void;
  activePanel: PanelType;
  onTogglePanel: (panel: PanelType) => void;
  sessionId: string | null;
  onSelectSession: (sid: string) => void;
  sessions: Session[];
  setSessions: (s: Session[]) => void;
  setMessages: (m: Message[]) => void;
  unreadCount: number;
  onOpenMessages: () => void;
}

// Stagger animation variants for session list items
const listContainerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.05,
    },
  },
};

const listItemVariants = {
  hidden: { opacity: 0, x: -12 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.25, ease: "easeOut" as const } },
};

export function Sidebar({
  darkMode, onToggleDark, activePanel, onTogglePanel,
  sessionId, onSelectSession, sessions, setSessions, setMessages,
  unreadCount, onOpenMessages,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [editingSid, setEditingSid] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number; message: string } | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    sessions: true,
    upload: false,
    knowledge: false,
  });
  const [balance, setBalance] = useState<number | null>(null);
  const { username, role } = useAuth();
  const isAdmin = role === 2;

  useEffect(() => {
    api.getBalance().then((res) => setBalance(res.balance)).catch(() => {});
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const res = searchQuery
        ? await api.searchSessions(searchQuery)
        : await api.getSessions();
      setSessions(res.sessions);
    } catch (e) {
      console.error("Failed to load sessions:", e);
    }
  }, [searchQuery, setSessions]);

  const loadDocuments = useCallback(async () => {
    try {
      const res = await api.getDocuments();
      setDocuments(res.documents);
    } catch (e) {
      console.error("Failed to load documents:", e);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (expandedSections.knowledge) loadDocuments();
  }, [expandedSections.knowledge, loadDocuments]);

  const handleNewSession = async () => {
    try {
      const res = await api.createSession();
      onSelectSession(res.session_id);
      setMessages([]);
      await loadSessions();
    } catch (e) {
      console.error("Failed to create session:", e);
    }
  };

  const handleDeleteSession = async (sid: string) => {
    try {
      await api.deleteSession(sid);
      if (sessionId === sid) {
        onSelectSession("");
        setMessages([]);
      }
      await loadSessions();
    } catch (e) {
      console.error("Failed to delete session:", e);
    }
  };

  const handleRenameSession = async (sid: string) => {
    if (!newTitle.trim()) return;
    try {
      await api.renameSession(sid, newTitle.trim());
      setEditingSid(null);
      await loadSessions();
    } catch (e) {
      console.error("Failed to rename session:", e);
    }
  };

  const handleSelectSession = async (sid: string) => {
    onSelectSession(sid);
    try {
      const res = await api.getSessionHistory(sid);
      setMessages(res.messages);
    } catch (e) {
      console.error("Failed to load history:", e);
    }
  };

  const handleUpload = async () => {
    if (!uploadFiles?.length) return;

    const mode = (localStorage.getItem("ocr_mode") as string) || "cloud";
    const token = api.getCloudOcrToken();

    setIsUploading(true);
    setUploadProgress({ current: 0, total: uploadFiles.length, message: "准备上传..." });

    if (mode === "cloud" && token) {
      try {
        for (let i = 0; i < uploadFiles.length; i++) {
          setUploadProgress({ current: i, total: uploadFiles.length, message: `正在云端 OCR 处理 ${uploadFiles[i].name}...` });
          await api.cloudOcrWeb(uploadFiles[i], token, (msg) => {
            setUploadProgress((prev) => prev ? { ...prev, message: msg } : null);
          });
        }
        setUploadFiles(null);
        await loadDocuments();
      } catch (e) {
        console.error("Cloud OCR failed:", e);
        alert(`云端 OCR 失败: ${e instanceof Error ? e.message : String(e)}`);
      } finally {
        setIsUploading(false);
        setUploadProgress(null);
      }
      return;
    }

    try {
      for (let i = 0; i < uploadFiles.length; i++) {
        setUploadProgress({ current: i, total: uploadFiles.length, message: `正在上传 ${uploadFiles[i].name}...` });
        await api.uploadDocument(uploadFiles[i]);
      }
      setUploadFiles(null);
      await loadDocuments();
    } catch (e) {
      console.error("Upload failed:", e);
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
    }
  };

  const handleDeleteDocument = async (docId: number) => {
    try {
      await api.deleteDocument(docId);
      await loadDocuments();
    } catch (e) {
      console.error("Failed to delete document:", e);
    }
  };

  const toggleSection = (key: string) => {
    setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const panelButtons: { key: PanelType; label: string; icon: React.ReactNode }[] = [
    { key: "mindmap", label: "导图", icon: <Map className="h-4 w-4" /> },
    { key: "quiz", label: "测验", icon: <FileQuestion className="h-4 w-4" /> },
    { key: "flashcard", label: "闪卡", icon: <Layers className="h-4 w-4" /> },
    { key: "stats", label: "统计", icon: <BarChart3 className="h-4 w-4" /> },
    { key: "compare", label: "对比", icon: <GitCompare className="h-4 w-4" /> },
    { key: "download", label: "下载", icon: <Download className="h-4 w-4" /> },
  ];

  return (
    <motion.div
      className="flex h-full flex-col overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <h1 className="text-lg font-semibold tracking-tight text-glow">智能学习助手</h1>
        <div className="flex items-center gap-1">
          <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
            <Button variant="ghost" size="icon" onClick={onOpenMessages} className="h-8 w-8 relative hover:bg-white/[0.06]">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <motion.span
                  className="absolute -top-0.5 -right-0.5 h-4 min-w-4 rounded-full bg-red-500 text-[10px] text-white flex items-center justify-center px-1"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 500, damping: 20 }}
                >
                  {unreadCount > 99 ? "99+" : unreadCount}
                </motion.span>
              )}
            </Button>
          </motion.div>
          <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
            <Button variant="ghost" size="icon" onClick={onToggleDark} className="h-8 w-8 hover:bg-white/[0.06]">
              <AnimatePresence mode="wait">
                {darkMode ? (
                  <motion.div key="sun" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.2 }}>
                    <Sun className="h-4 w-4" />
                  </motion.div>
                ) : (
                  <motion.div key="moon" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.2 }}>
                    <Moon className="h-4 w-4" />
                  </motion.div>
                )}
              </AnimatePresence>
            </Button>
          </motion.div>
        </div>
      </div>

      {/* User info & balance */}
      <div className="px-4 pb-3">
        <motion.div
          className="flex items-center justify-between rounded-xl px-3 py-2.5 glass-card"
          whileHover={{ scale: 1.01 }}
          transition={{ duration: 0.2 }}
        >
          <div className="flex items-center gap-2 min-w-0">
            {isAdmin ? (
              <Shield className="h-3.5 w-3.5 text-[#818cf8] shrink-0" />
            ) : (
              <span className="text-sm shrink-0">👤</span>
            )}
            <span className="text-xs font-medium truncate text-[#e2e8f0]">{username || "未登录"}</span>
            {isAdmin && (
              <Badge variant="default" className="text-[10px] px-1.5 py-0 bg-[#6366f1]/20 text-[#a5b4fc] border-[#6366f1]/30">管理</Badge>
            )}
          </div>
          <div className="flex items-center gap-1 text-xs shrink-0">
            <Wallet className="h-3 w-3 text-[#94a3b8]" />
            <span className={balance !== null && balance <= 0 ? "text-red-500 font-medium" : "text-[#94a3b8]"}>
              {balance !== null ? balance.toFixed(2) : "-"}
            </span>
          </div>
        </motion.div>
      </div>

      {/* Panel toggles */}
      <div className="flex flex-wrap gap-1.5 px-4 pb-3">
        {panelButtons.map(({ key, label, icon }, idx) => (
          <motion.div
            key={key}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.04 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Button
              variant="ghost"
              size="sm"
              className={`h-8 gap-1 text-xs border-0 rounded-lg transition-all duration-200 ${
                activePanel === key
                  ? "bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white shadow-[0_0_12px_rgba(99,102,241,0.3)]"
                  : "neu-button text-[#94a3b8] hover:text-[#e2e8f0]"
              }`}
              onClick={() => onTogglePanel(key)}
            >
              {icon}
              {activePanel === key ? `\u2715 ${label}` : label}
            </Button>
          </motion.div>
        ))}
      </div>

      {/* Separator */}
      <div className="mx-4 h-px" style={{ background: "linear-gradient(to right, transparent, rgba(99,102,241,0.2), transparent)" }} />

      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4 space-y-4">
          {/* New session */}
          <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}>
            <Button
              onClick={handleNewSession}
              className="w-full gap-2 h-9 rounded-xl border-0 font-medium
                bg-gradient-to-r from-[#6366f1] to-[#8b5cf6]
                hover:from-[#7c7ff7] hover:to-[#9d75f8]
                shadow-[0_4px_12px_rgba(99,102,241,0.25)]
                transition-all duration-300"
            >
              <Plus className="h-4 w-4" /> 新建会话
            </Button>
          </motion.div>

          {/* Sessions section */}
          <div>
            <button
              onClick={() => toggleSection("sessions")}
              className="flex w-full items-center gap-1.5 text-sm font-medium text-[#94a3b8] hover:text-[#e2e8f0] transition-colors"
            >
              <motion.div
                animate={{ rotate: expandedSections.sessions ? 0 : -90 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="h-3.5 w-3.5" />
              </motion.div>
              会话历史
            </button>
            <AnimatePresence initial={false}>
              {expandedSections.sessions && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                  className="overflow-hidden"
                >
                  <div className="mt-2 space-y-1">
                    <div className="relative mb-2">
                      <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[#64748b]" />
                      <Input
                        placeholder="搜索会话..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="glass-input h-8 pl-8 text-xs rounded-lg border-0 placeholder:text-[#64748b] focus-visible:ring-0 focus-visible:ring-offset-0"
                      />
                    </div>
                    <motion.div
                      variants={listContainerVariants}
                      initial="hidden"
                      animate="visible"
                    >
                      {sessions.map((s) => (
                        <motion.div
                          key={s.session_id}
                          variants={listItemVariants}
                          layout
                        >
                          {editingSid === s.session_id ? (
                            <div className="flex items-center gap-1">
                              <Input
                                value={newTitle}
                                onChange={(e) => setNewTitle(e.target.value)}
                                className="glass-input h-7 text-xs rounded-lg border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
                                autoFocus
                                onKeyDown={(e) => e.key === "Enter" && handleRenameSession(s.session_id)}
                              />
                              <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0 hover:bg-white/[0.06]" onClick={() => handleRenameSession(s.session_id)}>
                                <Check className="h-3.5 w-3.5 text-green-400" />
                              </Button>
                              <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0 hover:bg-white/[0.06]" onClick={() => setEditingSid(null)}>
                                <X className="h-3.5 w-3.5 text-[#94a3b8]" />
                              </Button>
                            </div>
                          ) : (
                            <div
                              className={`group flex cursor-pointer items-center gap-2 rounded-xl px-2.5 py-2 text-sm transition-all duration-200 hover:bg-white/[0.04] ${
                                sessionId === s.session_id
                                  ? "bg-gradient-to-r from-[#6366f1]/15 to-[#8b5cf6]/10 border border-[#6366f1]/20 font-medium shadow-[0_0_12px_rgba(99,102,241,0.08)]"
                                  : "border border-transparent"
                              }`}
                              onClick={() => handleSelectSession(s.session_id)}
                            >
                              <span className="flex-1 truncate">{s.title || "新会话"}</span>
                              <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                <Button
                                  size="icon" variant="ghost" className="h-6 w-6 hover:bg-white/[0.06]"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setEditingSid(s.session_id);
                                    setNewTitle(s.title || "");
                                  }}
                                >
                                  <Pencil className="h-3 w-3" />
                                </Button>
                                <Button
                                  size="icon" variant="ghost" className="h-6 w-6 text-destructive hover:bg-red-500/10"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteSession(s.session_id);
                                  }}
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          )}
                        </motion.div>
                      ))}
                    </motion.div>
                    {sessions.length === 0 && (
                      <motion.p
                        className="text-xs text-[#64748b] py-2 text-center"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                      >
                        {searchQuery ? "未找到会话" : "暂无会话"}
                      </motion.p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Separator */}
          <div className="h-px" style={{ background: "linear-gradient(to right, transparent, rgba(99,102,241,0.15), transparent)" }} />

          {/* Upload section */}
          <div>
            <button
              onClick={() => toggleSection("upload")}
              className="flex w-full items-center gap-1.5 text-sm font-medium text-[#94a3b8] hover:text-[#e2e8f0] transition-colors"
            >
              <motion.div
                animate={{ rotate: expandedSections.upload ? 0 : -90 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="h-3.5 w-3.5" />
              </motion.div>
              上传文件
            </button>
            <AnimatePresence initial={false}>
              {expandedSections.upload && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                  className="overflow-hidden"
                >
                  <div className="mt-2 space-y-2">
                    <motion.div
                      className="relative rounded-xl border border-dashed border-[#6366f1]/20 p-3 text-center hover:border-[#6366f1]/40 hover:bg-[#6366f1]/[0.03] transition-all duration-300 cursor-pointer"
                      whileHover={{ scale: 1.01 }}
                    >
                      <Input
                        type="file"
                        accept=".pdf"
                        multiple
                        onChange={(e) => setUploadFiles(e.target.files)}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                      />
                      <Upload className="h-5 w-5 mx-auto mb-1 text-[#6366f1]/50" />
                      <p className="text-xs text-[#64748b]">点击或拖拽 PDF 文件</p>
                    </motion.div>
                    {uploadFiles && uploadFiles.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                      >
                        <Button onClick={handleUpload} disabled={isUploading}
                          className="w-full h-8 text-xs rounded-lg border-0 bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] hover:from-[#7c7ff7] hover:to-[#9d75f8]"
                          size="sm"
                        >
                          <Upload className="h-3.5 w-3.5 mr-1" />
                          {isUploading ? "处理中..." : `导入知识库 (${uploadFiles.length} 个文件)`}
                        </Button>
                      </motion.div>
                    )}
                    <AnimatePresence>
                      {isUploading && uploadProgress && (
                        <motion.div
                          className="space-y-1"
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                        >
                          <div className="flex justify-between text-xs text-[#94a3b8]">
                            <span className="truncate flex-1">{uploadProgress.message}</span>
                            <span className="ml-2 shrink-0">{uploadProgress.current + 1}/{uploadProgress.total}</span>
                          </div>
                          <div className="w-full bg-black/20 rounded-full h-1.5 overflow-hidden">
                            <motion.div
                              className="bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] h-full rounded-full"
                              initial={{ width: 0 }}
                              animate={{ width: `${((uploadProgress.current + 1) / uploadProgress.total) * 100}%` }}
                              transition={{ duration: 0.4, ease: "easeOut" as const }}
                            />
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Separator */}
          <div className="h-px" style={{ background: "linear-gradient(to right, transparent, rgba(99,102,241,0.15), transparent)" }} />

          {/* Knowledge base section */}
          <div>
            <button
              onClick={() => toggleSection("knowledge")}
              className="flex w-full items-center gap-1.5 text-sm font-medium text-[#94a3b8] hover:text-[#e2e8f0] transition-colors"
            >
              <motion.div
                animate={{ rotate: expandedSections.knowledge ? 0 : -90 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="h-3.5 w-3.5" />
              </motion.div>
              知识库
            </button>
            <AnimatePresence initial={false}>
              {expandedSections.knowledge && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                  className="overflow-hidden"
                >
                  <div className="mt-2 space-y-1">
                    {documents.length > 0 ? (
                      <motion.div
                        variants={listContainerVariants}
                        initial="hidden"
                        animate="visible"
                      >
                        {documents.map((doc) => (
                          <motion.div
                            key={doc.id}
                            variants={listItemVariants}
                            className="flex items-center gap-2 rounded-xl px-2.5 py-2 text-xs group hover:bg-white/[0.03] transition-colors"
                          >
                            <span className={doc.status === "ready" ? "text-green-500" : doc.status === "error" ? "text-red-500" : "text-yellow-500"}>
                              {doc.status === "ready" ? "✅" : doc.status === "error" ? "❌" : "⏳"}
                            </span>
                            <span className="flex-1 truncate text-[#e2e8f0]">{doc.file_name}</span>
                            <span className="text-[#64748b]">{doc.chunks_count}块</span>
                            <Button
                              size="icon" variant="ghost" className="h-5 w-5 opacity-0 group-hover:opacity-100 text-destructive hover:bg-red-500/10 transition-opacity"
                              onClick={() => handleDeleteDocument(doc.id)}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </motion.div>
                        ))}
                      </motion.div>
                    ) : (
                      <motion.p
                        className="text-xs text-[#64748b] py-2 text-center"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                      >
                        暂无文档
                      </motion.p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </ScrollArea>

      {/* Settings, Admin, Logout & System status */}
      <div className="border-t border-white/[0.06] px-4 py-2 space-y-0.5">
        {isAdmin && (
          <motion.button
            onClick={() => onTogglePanel("admin")}
            className={`flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs transition-all duration-200 ${
              activePanel === "admin"
                ? "bg-gradient-to-r from-[#6366f1]/15 to-[#8b5cf6]/10 text-[#e2e8f0] font-medium border border-[#6366f1]/20"
                : "text-[#94a3b8] hover:bg-white/[0.04] hover:text-[#e2e8f0] border border-transparent"
            }`}
            whileHover={{ x: 2 }}
            transition={{ duration: 0.15 }}
          >
            <Shield className="h-3.5 w-3.5" />
            用户管理
          </motion.button>
        )}
        <motion.button
          onClick={() => onTogglePanel("settings")}
          className={`flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs transition-all duration-200 ${
            activePanel === "settings"
              ? "bg-gradient-to-r from-[#6366f1]/15 to-[#8b5cf6]/10 text-[#e2e8f0] font-medium border border-[#6366f1]/20"
              : "text-[#94a3b8] hover:bg-white/[0.04] hover:text-[#e2e8f0] border border-transparent"
          }`}
          whileHover={{ x: 2 }}
          transition={{ duration: 0.15 }}
        >
          <Settings className="h-3.5 w-3.5" />
          设置
        </motion.button>
        <motion.button
          onClick={() => {
            removeToken();
            window.location.href = "/login";
          }}
          className="flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs text-[#94a3b8] transition-all duration-200 hover:bg-red-500/10 hover:text-red-400 border border-transparent"
          whileHover={{ x: 2 }}
          transition={{ duration: 0.15 }}
        >
          <LogOut className="h-3.5 w-3.5" />
          退出登录
        </motion.button>
        <SystemStatus />
      </div>

    </motion.div>
  );
}

function SystemStatus() {
  const [status, setStatus] = useState<{ ok: boolean; checks: Record<string, boolean> } | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    api.getStatus().then((res) => {
      setStatus({ ok: res.status === "ok", checks: {} });
    }).catch(() => {
      setStatus({ ok: false, checks: {} });
    });
  }, [open]);

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1 text-xs text-[#64748b] hover:text-[#94a3b8] transition-colors py-1"
      >
        系统状态
        {status && (
          <span className={`ml-auto ${status.ok ? "text-green-500" : "text-red-500"}`}>
            {status.ok ? "● 正常" : "● 异常"}
          </span>
        )}
      </button>
    </div>
  );
}
