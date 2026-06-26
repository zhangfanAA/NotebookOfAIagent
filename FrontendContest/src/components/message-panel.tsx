"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Loader2, Mail, Send, Inbox, Clock,
  ChevronLeft, ChevronRight, CheckCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { SiteMessage, UserInfo } from "@/lib/types";
import * as api from "@/lib/api";

interface MessagePanelProps {
  userRole: number;
  onUnreadChange?: () => void;
}

const sectionVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 200, damping: 22 } },
};

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring" as const, stiffness: 250, damping: 25 } },
};

export function MessagePanel({ userRole, onUnreadChange }: MessagePanelProps) {
  const [activeTab, setActiveTab] = useState<"inbox" | "sent" | "compose">("inbox");

  const tabs = [
    { key: "inbox" as const, icon: <Inbox className="h-3.5 w-3.5" />, label: "收件箱" },
    { key: "sent" as const, icon: <Send className="h-3.5 w-3.5" />, label: "已发送" },
    { key: "compose" as const, icon: <Mail className="h-3.5 w-3.5" />, label: "写消息" },
  ];

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <motion.div
          className="flex items-center gap-2"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <Mail className="h-5 w-5 text-indigo-400" />
          <h1 className="text-2xl font-bold text-gradient">站内消息</h1>
        </motion.div>

        {/* Tab bar */}
        <motion.div
          className="glass-card rounded-2xl p-1.5 flex gap-1"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 rounded-xl py-2.5 text-xs font-medium transition-all relative",
                activeTab === tab.key
                  ? "text-[#e2e8f0]"
                  : "text-[#94a3b8] hover:text-[#e2e8f0]"
              )}
            >
              {activeTab === tab.key && (
                <motion.div
                  layoutId="msg-tab-bg"
                  className="absolute inset-0 rounded-xl bg-gradient-to-r from-indigo-500/15 to-violet-500/15 border border-indigo-400/20"
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
              <span className="relative z-10 flex items-center gap-1.5">
                {tab.icon}
                {tab.label}
              </span>
            </button>
          ))}
        </motion.div>

        <AnimatePresence mode="wait">
          {activeTab === "inbox" && <InboxTab key="inbox" onRead={onUnreadChange} />}
          {activeTab === "sent" && <SentTab key="sent" />}
          {activeTab === "compose" && <ComposeTab key="compose" userRole={userRole} />}
        </AnimatePresence>
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
    <motion.div
      className="glass-card rounded-2xl p-5"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-[#e2e8f0]">收件箱 ({total})</h3>
        {messages.some((m) => !m.is_read) && (
          <motion.button
            className="neu-button flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-[#94a3b8] hover:text-[#e2e8f0]"
            onClick={handleMarkAllRead}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            <CheckCheck className="h-3.5 w-3.5 text-indigo-400" /> 全部已读
          </motion.button>
        )}
      </div>

      {loading ? (
        <div className="shimmer-loading rounded-xl h-32" />
      ) : messages.length === 0 ? (
        <p className="text-center text-sm text-[#94a3b8] py-12">暂无消息</p>
      ) : (
        <motion.div
          className="space-y-2"
          variants={containerVariants}
          initial="hidden"
          animate="show"
        >
          {messages.map((m) => (
            <motion.div
              key={m.id}
              className={cn(
                "rounded-xl p-3.5 text-sm cursor-pointer transition-colors",
                !m.is_read
                  ? "glass-card glow-border border-indigo-400/20 hover:bg-indigo-500/[0.06]"
                  : "neu-inset hover:bg-white/[0.03]"
              )}
              onClick={() => !m.is_read && handleMarkRead(m.id)}
              variants={itemVariants}
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-[#e2e8f0]">{m.from_username || `用户${m.from_user_id}`}</span>
                  {!m.is_read && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">未读</span>
                  )}
                </div>
                <span className="text-xs text-[#94a3b8] flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {m.created_at ? new Date(m.created_at).toLocaleString("zh-CN", {
                    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
                  }) : "-"}
                </span>
              </div>
              <p className={cn("whitespace-pre-wrap", !m.is_read ? "text-[#e2e8f0]" : "text-[#94a3b8]")}>
                {m.content}
              </p>
            </motion.div>
          ))}
        </motion.div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/5">
          <span className="text-xs text-[#94a3b8]">第 {page} / {totalPages} 页</span>
          <div className="flex gap-1">
            <motion.button
              className="neu-button rounded-lg p-1.5 text-[#94a3b8] disabled:opacity-30"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </motion.button>
            <motion.button
              className="neu-button rounded-lg p-1.5 text-[#94a3b8] disabled:opacity-30"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </motion.button>
          </div>
        </div>
      )}
    </motion.div>
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
    <motion.div
      className="glass-card rounded-2xl p-5"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <h3 className="text-sm font-semibold text-[#e2e8f0] mb-4">已发送 ({total})</h3>

      {loading ? (
        <div className="shimmer-loading rounded-xl h-32" />
      ) : messages.length === 0 ? (
        <p className="text-center text-sm text-[#94a3b8] py-12">暂无消息</p>
      ) : (
        <motion.div
          className="space-y-2"
          variants={containerVariants}
          initial="hidden"
          animate="show"
        >
          {messages.map((m) => (
            <motion.div
              key={m.id}
              className="rounded-xl neu-inset p-3.5 text-sm"
              variants={itemVariants}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-medium text-[#e2e8f0]">致: {m.to_username || `用户${m.to_user_id}`}</span>
                <span className="text-xs text-[#94a3b8] flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {m.created_at ? new Date(m.created_at).toLocaleString("zh-CN", {
                    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
                  }) : "-"}
                </span>
              </div>
              <p className="text-[#94a3b8] whitespace-pre-wrap">{m.content}</p>
            </motion.div>
          ))}
        </motion.div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/5">
          <span className="text-xs text-[#94a3b8]">第 {page} / {totalPages} 页</span>
          <div className="flex gap-1">
            <motion.button
              className="neu-button rounded-lg p-1.5 text-[#94a3b8] disabled:opacity-30"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </motion.button>
            <motion.button
              className="neu-button rounded-lg p-1.5 text-[#94a3b8] disabled:opacity-30"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </motion.button>
          </div>
        </div>
      )}
    </motion.div>
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

  useEffect(() => {
    if (userRole === 2) {
      api.getUsers().then((res) => {
        setUsers(res.users.filter((u) => u.role !== 2));
      }).catch(() => {});
    }
  }, [userRole]);

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
    <motion.div
      className="glass-card rounded-2xl p-5 space-y-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <h3 className="text-sm font-semibold text-[#e2e8f0]">写消息</h3>

      {userRole === 2 ? (
        <div className="space-y-3">
          <label className="text-sm font-medium text-[#94a3b8]">收件人</label>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer text-[#94a3b8]">
              <input
                type="radio"
                name="target"
                checked={broadcast}
                onChange={() => { setBroadcast(true); setToUserId(0); }}
                className="accent-indigo-500"
              />
              所有用户
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer text-[#94a3b8]">
              <input
                type="radio"
                name="target"
                checked={!broadcast}
                onChange={() => setBroadcast(false)}
                className="accent-indigo-500"
              />
              指定用户
            </label>
          </div>
          {!broadcast && (
            <select
              className="glass-input w-full rounded-xl px-4 py-2.5 text-sm text-[#e2e8f0] outline-none"
              value={toUserId}
              onChange={(e) => setToUserId(Number(e.target.value))}
            >
              <option value={0} className="bg-[#0a0a1a]">请选择用户</option>
              {users.map((u) => (
                <option key={u.id} value={u.id} className="bg-[#0a0a1a]">{u.username}</option>
              ))}
            </select>
          )}
        </div>
      ) : (
        <div className="text-sm text-[#94a3b8]">
          收件人: <span className="font-medium text-[#e2e8f0]">管理员</span>
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium text-[#94a3b8]">消息内容</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="输入消息内容..."
          rows={4}
          className="glass-input w-full rounded-xl px-4 py-3 text-sm text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none resize-none"
        />
      </div>

      <AnimatePresence>
        {error && (
          <motion.p
            className="text-sm text-red-400"
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
          >
            {error}
          </motion.p>
        )}
        {success && (
          <motion.p
            className="text-sm text-emerald-400"
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
          >
            {success}
          </motion.p>
        )}
      </AnimatePresence>

      <motion.button
        onClick={handleSend}
        disabled={sending || !content.trim() || cooldown > 0 || (userRole === 2 && !broadcast && !toUserId)}
        className="flex items-center justify-center gap-1.5 rounded-xl px-6 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-indigo-500 to-violet-500 shadow-[0_0_20px_rgba(99,102,241,0.25)] hover:shadow-[0_0_30px_rgba(99,102,241,0.35)] transition-shadow disabled:opacity-40 disabled:cursor-not-allowed"
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.98 }}
      >
        {sending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
        {cooldown > 0 ? `${cooldown}秒后可发送` : broadcast ? "群发" : "发送"}
      </motion.button>
    </motion.div>
  );
}
