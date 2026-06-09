"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart3, TrendingUp, AlertTriangle, BookOpen, MessageSquare } from "lucide-react";
import type { LearningProgress } from "@/lib/types";
import * as api from "@/lib/api";

interface StatsPanelProps {
  sessionId: string | null;
}

export function StatsPanel({ sessionId }: StatsPanelProps) {
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [weakTopics, setWeakTopics] = useState<{ topic: string; question_count: number }[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [documents, setDocuments] = useState<{ name: string; chunks: number }[]>([]);

  const loadData = useCallback(async () => {
    if (!sessionId) return;
    try {
      const [progressRes, weakRes, topicsRes, docsRes] = await Promise.all([
        api.getLearningProgress(sessionId),
        api.getWeakTopics(sessionId),
        api.getSessionTopics(sessionId),
        api.getDocuments(),
      ]);
      console.log("[Stats] progress:", progressRes, "weak:", weakRes, "topics:", topicsRes);
      setProgress(progressRes);
      setWeakTopics(weakRes.weak_topics || []);
      setTopics((topicsRes.topics || []).map((t: { topic?: string } | string) => typeof t === "string" ? t : t.topic || ""));
      setDocuments(docsRes.documents.map((d) => ({ name: d.file_name, chunks: d.chunks_count })));
    } catch (e) {
      console.error("Failed to load stats:", e);
    }
  }, [sessionId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <h1 className="text-2xl font-bold">📊 学习统计</h1>

        {/* Overview cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">提问次数</CardTitle>
              <MessageSquare className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{progress?.total_questions ?? 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">平均置信度</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{progress ? Math.round(progress.avg_confidence * 100) : 0}%</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">知识缺口</CardTitle>
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{progress?.knowledge_gaps?.length ?? 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">文档数</CardTitle>
              <BookOpen className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{documents.length}</div>
            </CardContent>
          </Card>
        </div>

        {/* Weak topics */}
        {weakTopics.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">⚠️ 薄弱知识点</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {weakTopics.map((t, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-sm">{t.topic}</span>
                    <Badge variant="outline">{t.question_count} 次</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Topics covered */}
        {topics.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">📚 已学话题</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1.5">
                {topics.map((t, i) => (
                  <Badge key={i} variant="secondary">{t}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Document chunks chart */}
        {documents.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">📄 文档分块统计</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {documents.map((d, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="w-32 truncate text-sm">{d.name}</span>
                    <div className="flex-1">
                      <div className="h-4 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${Math.min(100, (d.chunks / Math.max(...documents.map((x) => x.chunks), 1)) * 100)}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground w-12 text-right">{d.chunks}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {!sessionId && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <BarChart3 className="h-12 w-12 mb-4 opacity-30" />
            <p>请先选择一个会话</p>
          </div>
        )}
      </div>
    </div>
  );
}
