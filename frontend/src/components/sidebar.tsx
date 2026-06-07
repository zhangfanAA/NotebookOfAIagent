"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sun, Moon, Plus, Search, Trash2, Pencil, Check, X,
  Map, FileQuestion, Layers, BarChart3, GitCompare,
  Upload, FileText, Database, ChevronDown, ChevronRight,
  Download, BookOpen, Bookmark, StickyNote, Heart, Settings, LogOut,
} from "lucide-react";
import type { PanelType, Session, Message, Document } from "@/lib/types";
import * as api from "@/lib/api";
import { removeToken, getUsername } from "@/lib/auth";

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
}

export function Sidebar({
  darkMode, onToggleDark, activePanel, onTogglePanel,
  sessionId, onSelectSession, sessions, setSessions, setMessages,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [editingSid, setEditingSid] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    sessions: true,
    upload: false,
    knowledge: false,
  });

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
    setIsUploading(true);
    try {
      for (let i = 0; i < uploadFiles.length; i++) {
        await api.uploadDocument(uploadFiles[i]);
      }
      setUploadFiles(null);
      await loadDocuments();
    } catch (e) {
      console.error("Upload failed:", e);
    } finally {
      setIsUploading(false);
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
  ];

  return (
    <div className="flex h-full flex-col overflow-hidden glass border-r border-sidebar-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <h1 className="text-lg font-semibold tracking-tight">📚 智能学习助手</h1>
        <Button variant="ghost" size="icon" onClick={onToggleDark} className="h-8 w-8">
          {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>

      {/* Panel toggles */}
      <div className="flex flex-wrap gap-1.5 px-4 pb-3">
        {panelButtons.map(({ key, label, icon }) => (
          <Button
            key={key}
            variant={activePanel === key ? "default" : "outline"}
            size="sm"
            className="h-8 gap-1 text-xs"
            onClick={() => onTogglePanel(key)}
          >
            {icon}
            {activePanel === key ? `✕ ${label}` : label}
          </Button>
        ))}
      </div>

      <Separator />

      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4 space-y-4">
          {/* New session */}
          <Button onClick={handleNewSession} className="w-full gap-2" variant="default">
            <Plus className="h-4 w-4" /> 新建会话
          </Button>

          {/* Sessions section */}
          <div>
            <button
              onClick={() => toggleSection("sessions")}
              className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              {expandedSections.sessions ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              💬 会话历史
            </button>
            {expandedSections.sessions && (
              <div className="mt-2 space-y-1">
                <div className="relative mb-2">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    placeholder="搜索会话..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-8 pl-8 text-xs"
                  />
                </div>
                {sessions.map((s) => (
                  <div key={s.session_id} className="group">
                    {editingSid === s.session_id ? (
                      <div className="flex items-center gap-1">
                        <Input
                          value={newTitle}
                          onChange={(e) => setNewTitle(e.target.value)}
                          className="h-7 text-xs"
                          autoFocus
                          onKeyDown={(e) => e.key === "Enter" && handleRenameSession(s.session_id)}
                        />
                        <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={() => handleRenameSession(s.session_id)}>
                          <Check className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={() => setEditingSid(null)}>
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ) : (
                      <div
                        className={`flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-accent ${
                          sessionId === s.session_id ? "bg-accent font-medium" : ""
                        }`}
                        onClick={() => handleSelectSession(s.session_id)}
                      >
                        <span className="flex-1 truncate">{s.title || "新会话"}</span>
                        <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button
                            size="icon" variant="ghost" className="h-6 w-6"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingSid(s.session_id);
                              setNewTitle(s.title || "");
                            }}
                          >
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button
                            size="icon" variant="ghost" className="h-6 w-6 text-destructive"
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
                  </div>
                ))}
                {sessions.length === 0 && (
                  <p className="text-xs text-muted-foreground py-2">{searchQuery ? "未找到会话" : "暂无会话"}</p>
                )}
              </div>
            )}
          </div>

          <Separator />

          {/* Upload section */}
          <div>
            <button
              onClick={() => toggleSection("upload")}
              className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              {expandedSections.upload ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              📤 上传课件
            </button>
            {expandedSections.upload && (
              <div className="mt-2 space-y-2">
                <Input
                  type="file"
                  accept=".pdf"
                  multiple
                  onChange={(e) => setUploadFiles(e.target.files)}
                  className="text-xs"
                />
                {uploadFiles && uploadFiles.length > 0 && (
                  <Button onClick={handleUpload} disabled={isUploading} className="w-full h-8 text-xs" size="sm">
                    <Upload className="h-3.5 w-3.5 mr-1" />
                    {isUploading ? "上传中..." : `导入知识库 (${uploadFiles.length} 个文件)`}
                  </Button>
                )}
              </div>
            )}
          </div>

          <Separator />

          {/* Knowledge base section */}
          <div>
            <button
              onClick={() => toggleSection("knowledge")}
              className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              {expandedSections.knowledge ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              🗄️ 知识库
            </button>
            {expandedSections.knowledge && (
              <div className="mt-2 space-y-1">
                {documents.length > 0 ? (
                  documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs group"
                    >
                      <span className={doc.status === "ready" ? "text-green-500" : doc.status === "error" ? "text-red-500" : "text-yellow-500"}>
                        {doc.status === "ready" ? "✅" : doc.status === "error" ? "❌" : "⏳"}
                      </span>
                      <span className="flex-1 truncate">{doc.file_name}</span>
                      <span className="text-muted-foreground">{doc.chunks_count}块</span>
                      <Button
                        size="icon" variant="ghost" className="h-5 w-5 opacity-0 group-hover:opacity-100 text-destructive"
                        onClick={() => handleDeleteDocument(doc.id)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground py-2">暂无文档</p>
                )}
              </div>
            )}
          </div>
        </div>
      </ScrollArea>

      {/* System status, Settings & Logout */}
      <div className="border-t px-4 py-2 space-y-1">
        <button
          onClick={() => onTogglePanel("settings")}
          className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs transition-colors hover:bg-accent ${
            activePanel === "settings" ? "bg-accent font-medium" : "text-muted-foreground"
          }`}
        >
          <Settings className="h-3.5 w-3.5" />
          ⚙️ 设置
        </button>
        <SystemStatus />
        <button
          onClick={() => {
            removeToken();
            window.location.href = "/login";
          }}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <LogOut className="h-3.5 w-3.5" />
          退出登录
        </button>
      </div>
    </div>
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
        className="flex w-full items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        🩺 系统状态
        {status && (
          <span className={`ml-auto ${status.ok ? "text-green-500" : "text-red-500"}`}>
            {status.ok ? "● 正常" : "● 异常"}
          </span>
        )}
      </button>
    </div>
  );
}
