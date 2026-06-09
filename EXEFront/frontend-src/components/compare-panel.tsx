"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, RefreshCw, GitCompare, CheckCircle, XCircle } from "lucide-react";
import * as api from "@/lib/api";

export function ComparePanel() {
  const [documents, setDocuments] = useState<{ id: number; name: string }[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [focus, setFocus] = useState("");
  const [result, setResult] = useState<{ similarities: string[]; differences: string[]; summary: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getDocuments().then((res) => {
      setDocuments(res.documents.filter((d) => d.status === "ready").map((d) => ({ id: d.id, name: d.file_name })));
    }).catch(() => {});
  }, []);

  const handleCompare = useCallback(async () => {
    if (selectedDocs.length < 2) return;
    setIsLoading(true);
    setError("");
    try {
      const res = await api.compareDocuments(selectedDocs, focus);
      if (res.status === "success") {
        setResult({ similarities: res.similarities || [], differences: res.differences || [], summary: res.summary || "" });
      } else {
        setError("对比失败");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, [selectedDocs, focus]);

  const toggleDoc = (docName: string) => {
    setSelectedDocs((prev) =>
      prev.includes(docName) ? prev.filter((d) => d !== docName) : [...prev, docName]
    );
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <h1 className="text-2xl font-bold">🔍 文档对比</h1>

        {/* Document selector */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">选择文档（至少 2 个）</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-1.5">
              {documents.map((doc) => (
                <Button
                  key={doc.id}
                  variant={selectedDocs.includes(doc.name) ? "default" : "outline"}
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => toggleDoc(doc.name)}
                >
                  {selectedDocs.includes(doc.name) && <CheckCircle className="h-3 w-3 mr-1" />}
                  {doc.name}
                </Button>
              ))}
              {documents.length === 0 && (
                <p className="text-sm text-muted-foreground">暂无可用文档</p>
              )}
            </div>

            <Input
              placeholder="对比焦点（可选）：如「概念定义」「公式推导」"
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              className="text-xs"
            />

            <Button
              onClick={handleCompare}
              disabled={isLoading || selectedDocs.length < 2}
              className="w-full h-9"
            >
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <GitCompare className="h-4 w-4 mr-2" />}
              开始对比
            </Button>
          </CardContent>
        </Card>

        {/* Error */}
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Summary */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">📋 对比总结</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.summary}</p>
              </CardContent>
            </Card>

            {/* Similarities */}
            {result.similarities && result.similarities.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    相似之处 ({result.similarities.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {result.similarities.map((s, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <Badge variant="outline" className="mt-0.5 shrink-0">{i + 1}</Badge>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {/* Differences */}
            {result.differences && result.differences.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-orange-500" />
                    不同之处 ({result.differences.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {result.differences.map((d, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <Badge variant="outline" className="mt-0.5 shrink-0">{i + 1}</Badge>
                        <span>{d}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {/* Reset */}
            <Button onClick={() => { setResult(null); setSelectedDocs([]); }} variant="outline" className="w-full">
              重新对比
            </Button>
          </div>
        )}

        {!result && !isLoading && !error && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <GitCompare className="h-12 w-12 mb-4 opacity-30" />
            <p>选择至少 2 个文档进行对比</p>
          </div>
        )}
      </div>
    </div>
  );
}
