"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Loader2, Download, Trash2, Upload, FileText, HardDrive } from "lucide-react";
import * as api from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { DownloadFile } from "@/lib/types";

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
    // 使用 fetch 下载以携带 token
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
        <div className="flex items-center gap-3">
          <Download className="h-6 w-6 text-primary" />
          <h2 className="text-2xl font-bold">文件下载</h2>
          <Badge variant="secondary">{files.length} 个文件</Badge>
        </div>

        {/* Admin upload area */}
        {isAdmin && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Upload className="h-4 w-4" />
                上传文件
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Input
                  type="file"
                  multiple
                  onChange={(e) => setUploadFile(e.target.files)}
                  className="text-xs"
                />
                {uploadFile && uploadFile.length > 0 && (
                  <Button onClick={handleUpload} disabled={isUploading} size="sm">
                    {isUploading ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-1" />
                    ) : (
                      <Upload className="h-4 w-4 mr-1" />
                    )}
                    {isUploading ? "上传中..." : `上传 (${uploadFile.length})`}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* File list */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <HardDrive className="h-4 w-4" />
              可下载文件
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : files.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">暂无可下载文件</p>
            ) : (
              <div className="space-y-2">
                {files.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center gap-3 rounded-lg border px-3 py-2.5 hover:bg-accent/50 transition-colors group"
                  >
                    <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file.file_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatSize(file.file_size)}
                        {file.uploaded_at && ` · ${file.uploaded_at.slice(0, 10)}`}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 gap-1 shrink-0"
                      onClick={() => handleDownload(file)}
                    >
                      <Download className="h-3.5 w-3.5" />
                      下载
                    </Button>
                    {isAdmin && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                        onClick={() => handleDelete(file.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
