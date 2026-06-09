"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Loader2, Mail, Send, Inbox, ArrowLeft, Clock,
  ChevronLeft, ChevronRight, CheckCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { SiteMessage, UserInfo } from "@/lib/types";
import * as api from "@/lib/api";

interface MessagePanelProps {
  userRole: number;
  onUnreadChange?: () => void;
}

export function MessagePanel({ userRole, onUnreadChange }: MessagePanelProps) {
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center gap-2">
          <Mail className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold">站内消息</h1>
        </div>
        <Tabs defaultValue="inbox" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="inbox" className="gap-1.5">
              <Inbox className="h-3.5 w-3.5" /> 收件箱
            </TabsTrigger>
            <TabsTrigger value="sent" className="gap-1.5">
              <Send className="h-3.5 w-3.5" /> 已发送
            </TabsTrigger>
            <TabsTrigger value="compose" className="gap-1.5">
              <Mail className="h-3.5 w-3.5" /> 写消息
            </TabsTrigger>
          </TabsList>
          <TabsContent value="inbox">
            <InboxTab onRead={onUnreadChange} />
          </TabsContent>
          <TabsContent value="sent">
            <SentTab />
          </TabsContent>
          <TabsContent value="compose">
            <ComposeTab userRole={userRole} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function InboxTab({ onRead }: { onRead?: () => void }) {
  const [messages, setMessages] = useState<SiteMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;
  const totalPages = Math.ceil(total / pageSize);

  const loadMessages = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getMessages("inbox", page, pageSize);
      setMessages(res.items);
      setTotal(res.total);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { loadMessages(); }, [loadMessages]);

  const handleMarkRead = async (id: number) => {
    try {
      await api.markMessageRead(id);
      setMessages((prev) => prev.map((m) => m.id === id ? { ...m, is_read: 1 } : m));
      onRead?.();
    } catch {
      // silent
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllRead();
      setMessages((prev) => prev.map((m) => ({ ...m, is_read: 1 })));
      onRead?.();
    } catch {
      // silent
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-medium">收件箱 ({total})</CardTitle>
        {messages.some((m) => !m.is_read) && (
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={handleMarkAllRead}>
            <CheckCheck className="h-3.5 w-3.5" /> 全部已读
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : messages.length === 0 ? (
          <p className="text-center text-sm text-muted-foreground py-12">暂无消息</p>
        ) : (
          <div className="space-y-2">
            {messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "rounded-lg border p-3 text-sm transition-colors cursor-pointer hover:bg-muted/50",
                  !m.is_read && "bg-primary/5 border-primary/20"
                )}
                onClick={() => !m.is_read && handleMarkRead(m.id)}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{m.from_username || `用户${m.from_user_id}`}</span>
                    {!m.is_read && (
                      <Badge variant="default" className="h-4 text-[10px] px-1.5">未读</Badge>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {m.created_at ? new Date(m.created_at).toLocaleString("zh-CN", {
                      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
                    }) : "-"}
                  </span>
                </div>
                <p className={cn("text-muted-foreground whitespace-pre-wrap", !m.is_read && "text-foreground")}>
                  {m.content}
                </p>
              </div>
            ))}
          </div>
        )}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t">
            <span className="text-xs text-muted-foreground">第 {page} / {totalPages} 页</span>
            <div className="flex gap-1">
              <Button variant="outline" size="sm" className="h-7" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button variant="outline" size="sm" className="h-7" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SentTab() {
  const [messages, setMessages] = useState<SiteMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;
  const totalPages = Math.ceil(total / pageSize);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const res = await api.getMessages("sent", page, pageSize);
        setMessages(res.items);
        setTotal(res.total);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    })();
  }, [page]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">已发送 ({total})</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : messages.length === 0 ? (
          <p className="text-center text-sm text-muted-foreground py-12">暂无消息</p>
        ) : (
          <div className="space-y-2">
            {messages.map((m) => (
              <div key={m.id} className="rounded-lg border p-3 text-sm">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium">致: {m.to_username || `用户${m.to_user_id}`}</span>
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {m.created_at ? new Date(m.created_at).toLocaleString("zh-CN", {
                      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
                    }) : "-"}
                  </span>
                </div>
                <p className="text-muted-foreground whitespace-pre-wrap">{m.content}</p>
              </div>
            ))}
          </div>
        )}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t">
            <span className="text-xs text-muted-foreground">第 {page} / {totalPages} 页</span>
            <div className="flex gap-1">
              <Button variant="outline" size="sm" className="h-7" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button variant="outline" size="sm" className="h-7" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ComposeTab({ userRole }: { userRole: number }) {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [toUserId, setToUserId] = useState<number>(0);
  const [broadcast, setBroadcast] = useState(false);
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  // 管理员：加载用户列表
  useEffect(() => {
    if (userRole === 2) {
      api.getUsers().then((res) => {
        setUsers(res.users.filter((u) => u.role !== 2));
      }).catch(() => {});
    }
  }, [userRole]);

  // 冷却计时器
  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setInterval(() => setCooldown((c) => c - 1), 1000);
    return () => clearInterval(t);
  }, [cooldown]);

  const handleSend = async () => {
    if (!content.trim()) return;
    try {
      setSending(true);
      setError("");
      setSuccess("");
      if (userRole === 2 && broadcast) {
        const res = await api.broadcastMessage(content.trim());
        setSuccess(`已群发给 ${res.count} 个用户`);
      } else {
        const targetId = userRole === 2 ? toUserId : 0;
        if (userRole === 2 && !targetId) {
          setError("请选择收件人");
          setSending(false);
          return;
        }
        await api.sendMessage(targetId, content.trim());
        setSuccess("发送成功");
      }
      setContent("");
      setCooldown(5);
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("频繁")) {
        setError(msg);
        setCooldown(5);
      } else {
        setError(msg);
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">写消息</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {userRole === 2 ? (
          <div className="space-y-3">
            <label className="text-sm font-medium">收件人</label>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="target"
                  checked={broadcast}
                  onChange={() => { setBroadcast(true); setToUserId(0); }}
                  className="accent-primary"
                />
                所有用户
              </label>
              <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="target"
                  checked={!broadcast}
                  onChange={() => setBroadcast(false)}
                  className="accent-primary"
                />
                指定用户
              </label>
            </div>
            {!broadcast && (
              <select
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={toUserId}
                onChange={(e) => setToUserId(Number(e.target.value))}
              >
                <option value={0}>请选择用户</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>{u.username}</option>
                ))}
              </select>
            )}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">
            收件人: <span className="font-medium text-foreground">管理员</span>
          </div>
        )}
        <div className="space-y-2">
          <label className="text-sm font-medium">消息内容</label>
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="输入消息内容..."
            rows={4}
            className="resize-none"
          />
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        {success && <p className="text-sm text-green-600">{success}</p>}
        <Button
          onClick={handleSend}
          disabled={sending || !content.trim() || cooldown > 0 || (userRole === 2 && !broadcast && !toUserId)}
          className="gap-1.5"
        >
          {sending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          {cooldown > 0 ? `${cooldown}秒后可发送` : broadcast ? "群发" : "发送"}
        </Button>
      </CardContent>
    </Card>
  );
}
