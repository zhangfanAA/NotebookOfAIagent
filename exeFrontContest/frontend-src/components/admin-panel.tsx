"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Loader2, Users, CreditCard, Activity, Search,
  ChevronLeft, ChevronRight, Shield, User, Ban, Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { UserInfo, UsageLog } from "@/lib/types";
import * as api from "@/lib/api";

function useAnimatedCounter(target: number, duration = 1000) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const animate = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, duration]);
  return value;
}

const sectionVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 200, damping: 22 } },
};

const rowVariants = {
  hidden: { opacity: 0, x: -10 },
  show: { opacity: 1, x: 0, transition: { type: "spring" as const, stiffness: 250, damping: 25 } },
};

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};

export function AdminPanel() {
  const [activeTab, setActiveTab] = useState<"users" | "logs" | "settings">("users");

  const tabs = [
    { key: "users" as const, icon: <Users className="h-3.5 w-3.5" />, label: "用户列表" },
    { key: "logs" as const, icon: <Activity className="h-3.5 w-3.5" />, label: "用量日志" },
    { key: "settings" as const, icon: <Settings className="h-3.5 w-3.5" />, label: "系统设置" },
  ];

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <motion.div
          className="flex items-center gap-2"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <Shield className="h-5 w-5 text-indigo-400" />
          <h1 className="text-2xl font-bold text-gradient">用户管理</h1>
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
                  layoutId="admin-tab-bg"
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
          {activeTab === "users" && <UsersTab key="users" />}
          {activeTab === "logs" && <LogsTab key="logs" />}
          {activeTab === "settings" && <SettingsTab key="settings" />}
        </AnimatePresence>
      </div>
    </div>
  );
}

function UsersTab() {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [banning, setBanning] = useState<number | null>(null);
  const [selectedUser, setSelectedUser] = useState<UserInfo | null>(null);
  const [adjustAmount, setAdjustAmount] = useState("");
  const [adjusting, setAdjusting] = useState(false);

  const userCount = useAnimatedCounter(users.length);

  const loadUsers = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await api.getUsers();
      setUsers(res.users);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const openAdjustDialog = (u: UserInfo) => {
    setSelectedUser(u);
    setAdjustAmount("");
    setDialogOpen(true);
  };

  const handleAdjustBalance = async () => {
    if (!selectedUser) return;
    const amount = parseFloat(adjustAmount);
    if (isNaN(amount) || amount === 0) return;
    try {
      setAdjusting(true);
      await api.addBalance(selectedUser.id, amount);
      setDialogOpen(false);
      setSelectedUser(null);
      setAdjustAmount("");
      await loadUsers();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdjusting(false);
    }
  };

  const handleToggleBan = async (userId: number, banned: boolean) => {
    try {
      setBanning(userId);
      await api.banUser(userId, banned);
      await loadUsers();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBanning(null);
    }
  };

  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <div className="glass-card rounded-2xl p-5">
          <div className="shimmer-loading rounded-xl h-48" />
        </div>
      </motion.div>
    );
  }

  if (error) {
    return (
      <motion.div
        className="glass-card rounded-2xl p-5 text-center text-sm text-red-400"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        {error}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="space-y-4"
    >
      <div className="glass-card rounded-2xl p-5">
        <h3 className="text-sm font-semibold text-[#e2e8f0] mb-4">全部用户 ({userCount})</h3>

        {/* Header row */}
        <div className="grid grid-cols-[2rem_1fr_80px_80px_100px_130px_130px_140px] gap-2 px-3 text-[10px] font-medium text-[#94a3b8] uppercase mb-2">
          <span>ID</span>
          <span>用户名</span>
          <span>角色</span>
          <span>状态</span>
          <span>余额</span>
          <span>最后上线</span>
          <span>注册时间</span>
          <span>操作</span>
        </div>

        <motion.div
          className="space-y-1"
          variants={containerVariants}
          initial="hidden"
          animate="show"
        >
          {users.map((u) => (
            <motion.div
              key={u.id}
              className={cn(
                "grid grid-cols-[2rem_1fr_80px_80px_100px_130px_130px_140px] items-center gap-2 rounded-xl px-3 py-2.5 text-sm hover:bg-white/[0.03] transition-colors",
                u.banned === 1 && "opacity-50"
              )}
              variants={rowVariants}
            >
              <span className="text-[#94a3b8] text-xs">{u.id}</span>
              <span className="flex items-center gap-1.5 font-medium truncate text-[#e2e8f0]">
                {u.role === 2 ? <Shield className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> : <User className="h-3.5 w-3.5 text-[#94a3b8] shrink-0" />}
                {u.username}
              </span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full w-fit font-medium ${
                u.role === 2
                  ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/20"
                  : "bg-white/5 text-[#94a3b8] border border-white/10"
              }`}>
                {u.role === 2 ? "管理员" : "用户"}
              </span>
              <span>
                {u.banned === 1 ? (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/20 flex items-center gap-0.5 w-fit">
                    <Ban className="h-2.5 w-2.5" /> 封禁
                  </span>
                ) : (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 w-fit">正常</span>
                )}
              </span>
              <span className="font-mono text-xs">
                <span className={u.balance <= 0 ? "text-red-400" : "text-emerald-400"}>
                  {u.balance.toFixed(2)}
                </span>
              </span>
              <span className="text-xs text-[#94a3b8]">
                {u.last_online_at
                  ? new Date(u.last_online_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
                  : "未登录"}
              </span>
              <span className="text-xs text-[#94a3b8]">
                {u.created_at ? new Date(u.created_at).toLocaleDateString("zh-CN") : "-"}
              </span>
              <div className="flex gap-1">
                <motion.button
                  className="neu-button flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-[#e2e8f0]"
                  onClick={() => openAdjustDialog(u)}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                >
                  <CreditCard className="h-3 w-3 text-indigo-400" />
                  调整
                </motion.button>
                {u.role !== 2 && (
                  <motion.button
                    className={cn(
                      "flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                      u.banned === 1
                        ? "neu-button text-[#e2e8f0]"
                        : "bg-red-500/15 text-red-400 border border-red-500/20 hover:bg-red-500/25"
                    )}
                    disabled={banning === u.id}
                    onClick={() => handleToggleBan(u.id, u.banned !== 1)}
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                  >
                    {banning === u.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : u.banned === 1 ? (
                      "解封"
                    ) : (
                      <><Ban className="h-3 w-3" /> 封号</>
                    )}
                  </motion.button>
                )}
              </div>
            </motion.div>
          ))}
          {users.length === 0 && (
            <p className="text-center text-sm text-[#94a3b8] py-8">暂无用户</p>
          )}
        </motion.div>
      </div>

      {/* Balance adjustment dialog */}
      <AnimatePresence>
        {dialogOpen && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setDialogOpen(false)} />
            <motion.div
              className="glass-card rounded-2xl p-6 w-full max-w-md relative z-10 space-y-4"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
            >
              <h3 className="text-lg font-semibold text-[#e2e8f0]">调整余额</h3>
              <p className="text-sm text-[#94a3b8]">
                为 <span className="font-semibold text-[#e2e8f0]">{selectedUser?.username}</span> 调整余额
                （当前：<span className={cn("font-mono font-semibold", (selectedUser?.balance ?? 0) <= 0 ? "text-red-400" : "text-emerald-400")}>
                  {selectedUser?.balance.toFixed(2)}
                </span> 元）
              </p>
              <div className="space-y-3">
                <label className="text-sm font-medium text-[#94a3b8]">调整金额</label>
                <input
                  type="number"
                  value={adjustAmount}
                  onChange={(e) => setAdjustAmount(e.target.value)}
                  placeholder="输入正数增加，负数扣减，如 10 或 -5"
                  className="glass-input w-full rounded-xl px-4 py-3 text-base text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none"
                  autoFocus
                  onKeyDown={(e) => e.key === "Enter" && handleAdjustBalance()}
                />
                <div className="flex gap-2">
                  {[10, 50, 100, 500].map((v) => (
                    <motion.button
                      key={v}
                      className="flex-1 neu-button rounded-xl py-2 text-xs font-medium text-[#e2e8f0]"
                      onClick={() => setAdjustAmount(String(v))}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                    >
                      +{v}
                    </motion.button>
                  ))}
                </div>
                <div className="flex gap-2">
                  {[-10, -50, -100].map((v) => (
                    <motion.button
                      key={v}
                      className="flex-1 neu-button rounded-xl py-2 text-xs font-medium text-red-400"
                      onClick={() => setAdjustAmount(String(v))}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                    >
                      {v}
                    </motion.button>
                  ))}
                  <div className="flex-1" />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <motion.button
                  className="neu-button rounded-xl px-4 py-2 text-sm text-[#94a3b8]"
                  onClick={() => setDialogOpen(false)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  取消
                </motion.button>
                <motion.button
                  className="rounded-xl px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-indigo-500 to-violet-500 shadow-[0_0_15px_rgba(99,102,241,0.2)] disabled:opacity-40"
                  onClick={handleAdjustBalance}
                  disabled={adjusting || !adjustAmount || parseFloat(adjustAmount) === 0}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {adjusting && <Loader2 className="h-4 w-4 animate-spin mr-1.5 inline" />}
                  确认调整
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function LogsTab() {
  const [logs, setLogs] = useState<UsageLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [filterUid, setFilterUid] = useState("");
  const pageSize = 20;

  const loadLogs = useCallback(async () => {
    try {
      setIsLoading(true);
      const uid = filterUid ? parseInt(filterUid) : undefined;
      const res = await api.getAdminUsageLogs(uid, page, pageSize);
      setLogs(res.items);
      setTotal(res.total);
    } catch {
      // silent
    } finally {
      setIsLoading(false);
    }
  }, [page, filterUid]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <motion.div
      className="glass-card rounded-2xl p-5"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-[#e2e8f0]">用量日志 ({total})</h3>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#94a3b8]" />
          <input
            placeholder="用户ID"
            value={filterUid}
            onChange={(e) => { setFilterUid(e.target.value); setPage(1); }}
            className="glass-input h-8 w-24 pl-8 pr-3 rounded-xl text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="shimmer-loading rounded-xl h-48" />
      ) : (
        <>
          <div className="space-y-1">
            <div className="grid grid-cols-[2rem_3rem_1fr_80px_80px_80px_140px] gap-2 px-3 text-[10px] font-medium text-[#94a3b8] uppercase">
              <span>ID</span>
              <span>UID</span>
              <span>模型</span>
              <span>输入</span>
              <span>输出</span>
              <span>费用</span>
              <span>时间</span>
            </div>
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="show"
            >
              {logs.map((log) => (
                <motion.div
                  key={log.id}
                  className="grid grid-cols-[2rem_3rem_1fr_80px_80px_80px_140px] gap-2 rounded-xl px-3 py-2 text-xs hover:bg-white/[0.03] transition-colors"
                  variants={rowVariants}
                >
                  <span className="text-[#94a3b8]">{log.id}</span>
                  <span className="text-[#94a3b8]">{log.user_id}</span>
                  <span className="truncate font-mono text-[#e2e8f0]">{log.model}</span>
                  <span className="text-[#94a3b8]">{log.prompt_tokens.toLocaleString()}</span>
                  <span className="text-[#94a3b8]">{log.completion_tokens.toLocaleString()}</span>
                  <span className="font-mono text-[#e2e8f0]">{log.cost.toFixed(4)}</span>
                  <span className="text-[#94a3b8]">
                    {new Date(log.created_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}
                  </span>
                </motion.div>
              ))}
            </motion.div>
            {logs.length === 0 && (
              <p className="text-center text-sm text-[#94a3b8] py-8">暂无日志</p>
            )}
          </div>

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
        </>
      )}
    </motion.div>
  );
}

function SettingsTab() {
  const [allowRegistration, setAllowRegistration] = useState(true);
  const [paddleOcrWebEnabled, setPaddleOcrWebEnabled] = useState(true);
  const [paddleOcrAppEnabled, setPaddleOcrAppEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getRegistrationSetting(),
      api.getPaddleOcrSetting(),
    ]).then(([regRes, paddleRes]) => {
      setAllowRegistration(regRes.allow_registration);
      setPaddleOcrWebEnabled(paddleRes.web_enabled);
      setPaddleOcrAppEnabled(paddleRes.app_enabled);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleToggleRegistration = async () => {
    try {
      setSaving("registration");
      const newValue = !allowRegistration;
      await api.updateRegistrationSetting(newValue);
      setAllowRegistration(newValue);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(null);
    }
  };

  const handleTogglePaddleOcrWeb = async () => {
    try {
      setSaving("paddle-ocr-web");
      const newValue = !paddleOcrWebEnabled;
      await api.updatePaddleOcrSetting({ web_enabled: newValue });
      setPaddleOcrWebEnabled(newValue);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(null);
    }
  };

  const handleTogglePaddleOcrApp = async () => {
    try {
      setSaving("paddle-ocr-app");
      const newValue = !paddleOcrAppEnabled;
      await api.updatePaddleOcrSetting({ app_enabled: newValue });
      setPaddleOcrAppEnabled(newValue);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <div className="glass-card rounded-2xl p-5">
          <div className="shimmer-loading rounded-xl h-32" />
        </div>
      </motion.div>
    );
  }

  const toggleItems = [
    {
      label: "开放注册",
      desc: "关闭后新用户将无法注册账号",
      checked: allowRegistration,
      onChange: handleToggleRegistration,
      savingKey: "registration",
      statusText: allowRegistration ? "已开放注册" : "注册已关闭",
    },
    {
      label: "启用 PaddleOCR（云端）",
      desc: "启用后云端上传 PDF 支持扫描型文字识别，关闭则只支持文字型 PDF",
      checked: paddleOcrWebEnabled,
      onChange: handleTogglePaddleOcrWeb,
      savingKey: "paddle-ocr-web",
      statusText: paddleOcrWebEnabled ? "已启用（支持扫描型 PDF）" : "已禁用（仅支持文字型 PDF）",
    },
    {
      label: "启用 PaddleOCR（本地端）",
      desc: "启用后本地客户端上传 PDF 支持扫描型文字识别，关闭则只支持文字型 PDF",
      checked: paddleOcrAppEnabled,
      onChange: handleTogglePaddleOcrApp,
      savingKey: "paddle-ocr-app",
      statusText: paddleOcrAppEnabled ? "已启用（支持扫描型 PDF）" : "已禁用（仅支持文字型 PDF）",
    },
  ];

  return (
    <motion.div
      className="glass-card rounded-2xl p-5 space-y-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <h3 className="text-sm font-semibold text-[#e2e8f0]">系统设置</h3>

      {toggleItems.map((item, idx) => (
        <motion.div
          key={item.savingKey}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: idx * 0.05 }}
        >
          <div className="flex items-center justify-between rounded-xl neu-inset p-4">
            <div className="space-y-0.5">
              <div className="text-sm font-medium text-[#e2e8f0]">{item.label}</div>
              <div className="text-xs text-[#94a3b8]">{item.desc}</div>
            </div>
            <button
              onClick={item.onChange}
              disabled={saving !== null}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-all duration-300 ease-in-out focus:outline-none ${
                item.checked
                  ? "bg-gradient-to-r from-indigo-500 to-violet-500 shadow-[0_0_12px_rgba(99,102,241,0.3)]"
                  : "bg-white/10"
              } ${saving === item.savingKey ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <motion.span
                className="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg"
                animate={{ x: item.checked ? 20 : 0 }}
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
              />
            </button>
          </div>
          <div className="text-xs text-[#94a3b8]/60 mt-1.5 ml-1">当前状态：{item.statusText}</div>
        </motion.div>
      ))}

      {/* Server OCR (disabled) */}
      <div>
        <div className="flex items-center justify-between rounded-xl neu-inset p-4 opacity-50">
          <div className="space-y-0.5">
            <div className="text-sm font-medium text-[#e2e8f0] flex items-center gap-2">
              启用服务器 OCR
              <span className="text-[10px] px-1.5 py-0 rounded bg-white/10 text-[#94a3b8]">待开发</span>
            </div>
            <div className="text-xs text-[#94a3b8]">启用后可通过独立 OCR 服务器处理扫描型 PDF</div>
          </div>
          <button
            disabled
            className="relative inline-flex h-6 w-11 shrink-0 cursor-not-allowed rounded-full border-2 border-transparent bg-white/10"
          >
            <span className="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg translate-x-0" />
          </button>
        </div>
        <div className="text-xs text-[#94a3b8]/60 mt-1.5 ml-1">当前状态：未启用（功能开发中）</div>
      </div>
    </motion.div>
  );
}
