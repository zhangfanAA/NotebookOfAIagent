"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Download, Trash2, Upload, FileText, HardDrive } from "lucide-react";
import * as api from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { DownloadFile } from "@/lib/types";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16, scale: 0.97 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring" as const, stiffness: 200, damping: 22 } },
};

function getFileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return { color: "from-red-500 to-rose-600", glow: "shadow-red-500/20" };
  if (ext === "docx" || ext === "doc") return { color: "from-blue-500 to-indigo-600", glow: "shadow-blue-500/20" };
  if (ext === "xlsx" || ext === "xls") return { color: "from-emerald-500 to-green-600", glow: "shadow-emerald-500/20" };
  if (ext === "pptx" || ext === "ppt") return { color: "from-amber-500 to-orange-600", glow: "shadow-amber-500/20" };
  if (ext === "zip" || ext === "rar") return { color: "from-purple-500 to-violet-600", glow: "shadow-purple-500/20" };
  return { color: "from-slate-500 to-gray-600", glow: "shadow-slate-500/20" };
}

export function DownloadPanel() {
  const [files, setFiles] = useState<DownloadFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadFile, setUploadFile] = useState<FileList | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    try {
      const token = getToken();
      if (token) {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setIsAdmin(payload.role === 2);
      }
    } catch {}
  }, []);

  const loadFiles = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await api.getDownloadFiles();
      setFiles(res.files);
    } catch (e) {
      console.error("Failed to load download files:", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handleUpload = async () => {
    if (!uploadFile?.length) return;
    setIsUploading(true);
    try {
      for (let i = 0; i < uploadFile.length; i++) {
        await api.uploadDownloadFile(uploadFile[i]);
      }
      setUploadFile(null);
      await loadFiles();
    } catch (e) {
      console.error("Upload failed:", e);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteDownloadFile(id);
      await loadFiles();
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  const handleDownload = (file: DownloadFile) => {
    const token = getToken();
    const url = api.getDownloadFileUrl(file.id);
    fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = file.file_name;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch((e) => console.error("Download failed:", e));
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <motion.div
          className="flex items-center gap-3"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <Download className="h-6 w-6 text-indigo-400" />
          <h2 className="text-2xl font-bold text-gradient">文件下载</h2>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-primary/10 text-indigo-300 border border-primary/20 font-medium">
            {files.length} 个文件
          </span>
        </motion.div>

        {/* Admin upload area */}
        <AnimatePresence>
          {isAdmin && (
            <motion.div
              className="glass-card rounded-2xl p-5"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ delay: 0.1 }}
            >
              <h3 className="text-sm font-semibold text-[#e2e8f0] flex items-center gap-2 mb-3">
                <Upload className="h-4 w-4 text-indigo-400" />
                上传文件
              </h3>
              <div className="flex items-center gap-3">
                <label className="flex-1 flex items-center justify-center gap-2 rounded-xl border-2 border-dashed border-white/10 bg-white/[0.02] p-4 text-xs text-[#94a3b8] hover:border-indigo-400/30 hover:text-[#e2e8f0] transition-colors cursor-pointer">
                  <Upload className="h-4 w-4" />
                  {uploadFile && uploadFile.length > 0
                    ? `已选择 ${uploadFile.length} 个文件`
                    : "点击或拖拽文件到此处"
                  }
                  <input
                    type="file"
                    multiple
                    className="hidden"
                    onChange={(e) => setUploadFile(e.target.files)}
                  />
                </label>
                {uploadFile && uploadFile.length > 0 && (
                  <motion.button
                    onClick={handleUpload}
                    disabled={isUploading}
                    className="neu-button flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-medium text-[#e2e8f0] disabled:opacity-40"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {isUploading ? (
                      <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                    ) : (
                      <Upload className="h-4 w-4 text-indigo-400" />
                    )}
                    {isUploading ? "上传中..." : `上传 (${uploadFile.length})`}
                  </motion.button>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* File list */}
        <motion.div
          className="glass-card rounded-2xl p-5"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <h3 className="text-sm font-semibold text-[#e2e8f0] flex items-center gap-2 mb-3">
            <HardDrive className="h-4 w-4 text-indigo-400" />
            可下载文件
          </h3>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="shimmer-loading rounded-xl w-full h-16" />
            </div>
          ) : files.length === 0 ? (
            <p className="text-sm text-[#94a3b8] text-center py-12">暂无可下载文件</p>
          ) : (
            <motion.div
              className="space-y-2"
              variants={containerVariants}
              initial="hidden"
              animate="show"
            >
              {files.map((file) => {
                const iconStyle = getFileIcon(file.file_name);
                return (
                  <motion.div
                    key={file.id}
                    className="flex items-center gap-3 rounded-xl px-4 py-3 glass-card group hover:bg-white/[0.04] transition-colors"
                    variants={itemVariants}
                  >
                    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${iconStyle.color} shadow-lg ${iconStyle.glow}`}>
                      <FileText className="h-4 w-4 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate text-[#e2e8f0]">{file.file_name}</p>
                      <p className="text-xs text-[#94a3b8]">
                        {formatSize(file.file_size)}
                        {file.uploaded_at && ` \u00b7 ${file.uploaded_at.slice(0, 10)}`}
                      </p>
                    </div>
                    <motion.button
                      className="neu-button flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium text-[#e2e8f0] shrink-0"
                      onClick={() => handleDownload(file)}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                    >
                      <Download className="h-3.5 w-3.5 text-indigo-400" />
                      下载
                    </motion.button>
                    {isAdmin && (
                      <motion.button
                        className="flex items-center justify-center h-8 w-8 rounded-xl text-red-400/60 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                        onClick={() => handleDelete(file.id)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </motion.button>
                    )}
                  </motion.div>
                );
              })}
            </motion.div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
