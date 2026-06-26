"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Save, Check, X, Server, Cloud, CreditCard, Eye, EyeOff, Wallet, Coins, ScanLine, Bot, Palette, Upload, Image, Zap } from "lucide-react";
import type { LlmSettings } from "@/lib/types";
import * as api from "@/lib/api";
import { getRole } from "@/lib/auth";

interface SettingsPanelProps {
  bgTheme?: string;
  bgImage?: string;
  onBgChange?: (themeId: string) => void;
  onBgImageUpload?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  bgThemes?: { id: string; label: string; className: string }[];
}

const sectionVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 200, damping: 22 } },
};

function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onChange}
      disabled={disabled}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-all duration-300 ease-in-out focus:outline-none ${
        checked
          ? "bg-gradient-to-r from-indigo-500 to-violet-500 shadow-[0_0_12px_rgba(99,102,241,0.3)]"
          : "bg-white/10"
      } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <motion.span
        className="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg"
        animate={{ x: checked ? 20 : 0 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
      />
    </button>
  );
}

export function SettingsPanel({ bgTheme, bgImage, onBgChange, onBgImageUpload, bgThemes }: SettingsPanelProps) {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  const [provider, setProvider] = useState<"local" | "cloud" | "balance">("local");
  const [cloudUrl, setCloudUrl] = useState("");
  const [cloudKey, setCloudKey] = useState("");
  const [cloudModel, setCloudModel] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [balanceUrl, setBalanceUrl] = useState("");
  const [balanceKey, setBalanceKey] = useState("");
  const [balanceModel, setBalanceModel] = useState("");
  const [showBalanceKey, setShowBalanceKey] = useState(false);
  const [balance, setBalance] = useState<number | null>(null);
  const [ocrMode, setOcrMode] = useState<"cloud" | "balance" | "server">(() => {
    if (typeof window === "undefined") return "cloud";
    return (localStorage.getItem("ocr_mode") as "cloud" | "balance" | "server") || "cloud";
  });
  const [cloudOcrToken, setCloudOcrToken] = useState(() => api.getCloudOcrToken());
  const [showOcrToken, setShowOcrToken] = useState(false);
  const [agentVisualization, setAgentVisualization] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("agent_mode") === "true";
  });

  const [isAdmin, setIsAdmin] = useState(false);
  const [balanceOcrKey, setBalanceOcrKey] = useState("");
  const [showBalanceOcrKey, setShowBalanceOcrKey] = useState(false);
  const [adminBalanceKey, setAdminBalanceKey] = useState("");
  const [adminBalanceUrl, setAdminBalanceUrl] = useState("");
  const [adminBalanceModel, setAdminBalanceModel] = useState("");
  const [showAdminBalanceKey, setShowAdminBalanceKey] = useState(false);
  const [ocrTestResult, setOcrTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [modelTestResult, setModelTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [cloudTestResult, setCloudTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [ocrConfigured, setOcrConfigured] = useState(false);

  useEffect(() => {
    api.getBalance().then((res) => setBalance(res.balance)).catch(() => {});
    if (getRole() === 2) {
      setIsAdmin(true);
      api.getBalanceOcrConfig().then((res) => {
        setOcrConfigured(!!res.api_key);
      }).catch(() => {});
      api.getBalanceModelConfig().then((res) => {
        setAdminBalanceUrl(res.base_url || "");
        setAdminBalanceModel(res.model || "");
      }).catch(() => {});
    }
  }, []);

  useEffect(() => {
    api.getLlmSettings().then((res) => {
      setSettings(res);
      setProvider(res.provider);
      setCloudUrl(res.cloud.base_url);
      setCloudKey("");
      setCloudModel(res.cloud.model);
      setBalanceUrl(res.balance.base_url);
      setBalanceKey("");
      setBalanceModel(res.balance.model);
    }).catch(() => {}).finally(() => setIsLoading(false));
  }, []);

  const toggleAgentVisualization = () => {
    const next = !agentVisualization;
    setAgentVisualization(next);
    localStorage.setItem("agent_mode", String(next));
    window.dispatchEvent(new Event("agent-mode-changed"));
  };

  const handleTestOcr = async () => {
    setTesting("ocr");
    setOcrTestResult(null);
    try {
      const res = await api.testOcrConnection();
      setOcrTestResult({ ok: res.ok, msg: res.message });
    } catch (e) {
      setOcrTestResult({ ok: false, msg: (e as Error).message });
    } finally {
      setTesting(null);
    }
  };

  const handleTestBalanceModel = async () => {
    setTesting("model");
    setModelTestResult(null);
    try {
      const res = await api.testBalanceModelConnection();
      setModelTestResult({ ok: res.ok, msg: res.message });
    } catch (e) {
      setModelTestResult({ ok: false, msg: (e as Error).message });
    } finally {
      setTesting(null);
    }
  };

  const handleTestCloud = async () => {
    setTesting("cloud");
    setCloudTestResult(null);
    try {
      const res = await api.testCloudConnection({
        cloud_api_key: cloudKey || undefined,
        cloud_base_url: cloudUrl || undefined,
        cloud_model: cloudModel || undefined,
      });
      setCloudTestResult({ ok: res.ok, msg: res.message });
    } catch (e) {
      setCloudTestResult({ ok: false, msg: (e as Error).message });
    } finally {
      setTesting(null);
    }
  };

  const handleSaveBalanceOcr = async () => {
    try {
      await api.updateBalanceOcrConfig(balanceOcrKey);
      setBalanceOcrKey("");
      alert("余额 OCR API Key 已保存");
    } catch (e) {
      alert("保存失败: " + (e as Error).message);
    }
  };

  const handleSaveBalanceModel = async () => {
    try {
      await api.updateBalanceModelConfig({
        balance_api_key: adminBalanceKey || undefined,
        balance_base_url: adminBalanceUrl || undefined,
        balance_model: adminBalanceModel || undefined,
      });
      setAdminBalanceKey("");
      alert("余额模型配置已保存");
    } catch (e) {
      alert("保存失败: " + (e as Error).message);
    }
  };

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    setSaveMsg("");
    try {
      const data: {
        provider: "local" | "cloud" | "balance";
        cloud_base_url?: string;
        cloud_api_key?: string;
        cloud_model?: string;
        balance_api_key?: string;
        balance_base_url?: string;
        balance_model?: string;
      } = { provider };
      if (provider === "cloud") {
        data.cloud_base_url = cloudUrl;
        if (cloudKey) data.cloud_api_key = cloudKey;
        data.cloud_model = cloudModel;
      }
      if (provider === "balance") {
        data.balance_base_url = balanceUrl;
        if (balanceKey) data.balance_api_key = balanceKey;
        data.balance_model = balanceModel;
      }
      await api.updateLlmSettings(data);
      setSaveMsg("保存成功，刷新后生效");
      setTimeout(() => setSaveMsg(""), 3000);
    } catch (e) {
      setSaveMsg("保存失败: " + (e as Error).message);
    } finally {
      setIsSaving(false);
    }
  }, [provider, cloudUrl, cloudKey, cloudModel, balanceUrl, balanceKey, balanceModel]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl space-y-6">
        <motion.h1
          className="text-2xl font-bold text-gradient"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          设置
        </motion.h1>

        {/* Account balance */}
        <motion.div
          className="glass-card rounded-2xl p-4"
          variants={sectionVariants}
          initial="hidden"
          animate="show"
          transition={{ delay: 0.05 }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Wallet className="h-4 w-4 text-indigo-400" />
              <span className="text-sm text-[#94a3b8]">账号余额</span>
            </div>
            <span className={`text-lg font-semibold ${balance !== null && balance <= 0 ? "text-red-400" : "text-[#e2e8f0]"}`}>
              {balance !== null ? `\u00a5 ${balance.toFixed(2)}` : "-"}
            </span>
          </div>
        </motion.div>

        {/* OCR settings */}
        <motion.div
          className="glass-card rounded-2xl p-5 space-y-4"
          variants={sectionVariants}
          initial="hidden"
          animate="show"
          transition={{ delay: 0.1 }}
        >
          <h3 className="text-sm font-semibold text-[#e2e8f0] flex items-center gap-2">
            <ScanLine className="h-4 w-4 text-indigo-400" />
            OCR 文字识别
          </h3>
          <div className="flex gap-2">
            {(["cloud", "balance", "server"] as const).map((mode) => (
              <motion.button
                key={mode}
                onClick={() => {
                  if (mode !== "server") {
                    setOcrMode(mode);
                    localStorage.setItem("ocr_mode", mode);
                  }
                }}
                disabled={mode === "server"}
                className={`flex-1 flex items-center justify-center gap-1.5 rounded-xl py-2 text-xs font-medium transition-all ${
                  ocrMode === mode
                    ? "bg-gradient-to-r from-indigo-500/20 to-violet-500/20 border border-indigo-400/30 text-indigo-200"
                    : mode === "server"
                    ? "neu-button text-[#94a3b8]/40 cursor-not-allowed"
                    : "neu-button text-[#94a3b8]"
                }`}
                whileHover={mode !== "server" ? { scale: 1.02 } : {}}
                whileTap={mode !== "server" ? { scale: 0.98 } : {}}
              >
                {mode === "cloud" && "云端 OCR"}
                {mode === "balance" && (
                  <>
                    <Coins className="h-3 w-3" />
                    余额 OCR
                  </>
                )}
                {mode === "server" && (
                  <>
                    服务器 OCR
                    <span className="text-[9px] px-1 py-0 rounded bg-white/10 ml-1">待开发</span>
                  </>
                )}
              </motion.button>
            ))}
          </div>
          {ocrMode === "cloud" && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#94a3b8]">云端 OCR Token</label>
              <div className="relative">
                <input
                  type={showOcrToken ? "text" : "password"}
                  value={cloudOcrToken}
                  onChange={(e) => { setCloudOcrToken(e.target.value); api.setCloudOcrToken(api.extractBearerToken(e.target.value)); }}
                  placeholder="粘贴 Bearer Token 或 API Key"
                  className="glass-input w-full rounded-xl px-4 py-2.5 text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowOcrToken(!showOcrToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94a3b8] hover:text-[#e2e8f0]"
                >
                  {showOcrToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
              <p className="text-[10px] text-[#94a3b8]/60">用于扫描型 PDF 的文字识别，支持 PaddleOCR-VL 云端 API</p>
            </div>
          )}
          {ocrMode === "balance" && (
            <div className="rounded-xl bg-indigo-500/10 border border-indigo-500/20 p-3 text-xs text-indigo-300">
              <div className="flex items-center gap-2 mb-1">
                <Coins className="h-3.5 w-3.5" />
                <span className="font-medium">余额 OCR 模式</span>
              </div>
              <p>每页 PDF / 每张图片消耗 <span className="font-semibold">\u00a50.005</span>，自动从账号余额扣除。</p>
              <p className="mt-1 text-[10px] text-indigo-300/60">API 由管理员统一配置，无需手动填写。</p>
            </div>
          )}
          {ocrMode === "server" && (
            <div className="rounded-xl neu-inset p-3 text-xs text-[#94a3b8]">服务器 OCR 功能开发中，敬请期待</div>
          )}
        </motion.div>

        {/* Model provider selection */}
        <motion.div
          className="glass-card rounded-2xl p-5 space-y-4"
          variants={sectionVariants}
          initial="hidden"
          animate="show"
          transition={{ delay: 0.15 }}
        >
          <h3 className="text-sm font-semibold text-[#e2e8f0]">模型提供商</h3>
          <div className="grid grid-cols-3 gap-3">
            {([
              { key: "local" as const, icon: <Server className="h-6 w-6 mb-2 text-[#94a3b8]" />, label: "本地模型", sub: "Ollama" },
              { key: "cloud" as const, icon: <Cloud className="h-6 w-6 mb-2 text-[#94a3b8]" />, label: "云端模型", sub: "自备 Key" },
              { key: "balance" as const, icon: <Coins className="h-6 w-6 mb-2 text-[#94a3b8]" />, label: "余额模型", sub: "按量扣费" },
            ]).map((p) => (
              <motion.button
                key={p.key}
                onClick={() => setProvider(p.key)}
                className={`relative rounded-2xl p-4 text-left transition-all ${
                  provider === p.key
                    ? "glass-card glow-border border-indigo-400/30 shadow-[0_0_20px_rgba(99,102,241,0.12)]"
                    : "neu-button"
                }`}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                {provider === p.key && (
                  <motion.div
                    className="absolute top-2 right-2"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 500, damping: 25 }}
                  >
                    <Check className="h-4 w-4 text-indigo-400" />
                  </motion.div>
                )}
                {p.icon}
                <p className="text-sm font-medium text-[#e2e8f0]">{p.label}</p>
                <p className="text-[10px] text-[#94a3b8] mt-1">{p.sub}</p>
                {p.key === "local" && settings && (
                  <div className="mt-2 space-y-0.5">
                    <p className="text-[10px] text-[#94a3b8]/60 truncate">模型: {settings.local.model}</p>
                    <p className="text-[10px] text-[#94a3b8]/60 truncate">地址: {settings.local.base_url}</p>
                  </div>
                )}
              </motion.button>
            ))}
          </div>
        </motion.div>

        {/* Cloud config */}
        <AnimatePresence>
          {provider === "cloud" && (
            <motion.div
              className="glass-card rounded-2xl p-5 space-y-3"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ type: "spring", stiffness: 200, damping: 25 }}
            >
              <h3 className="text-sm font-semibold text-[#e2e8f0]">云端 API 配置</h3>
              <div className="rounded-xl neu-inset p-3 text-xs text-[#94a3b8]">
                自备 API Key，支持所有 OpenAI 兼容格式（DeepSeek、OpenAI、Moonshot 等）
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#94a3b8]">API Base URL</label>
                <input
                  value={cloudUrl}
                  onChange={(e) => setCloudUrl(e.target.value)}
                  placeholder="https://api.deepseek.com/v1"
                  className="glass-input w-full rounded-xl px-4 py-2.5 text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#94a3b8]">API Key</label>
                <div className="relative">
                  <input
                    type={showKey ? "text" : "password"}
                    value={cloudKey}
                    onChange={(e) => setCloudKey(e.target.value)}
                    placeholder={settings?.cloud.api_key ? "已配置（留空保持不变）" : "sk-..."}
                    className="glass-input w-full rounded-xl px-4 py-2.5 text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94a3b8] hover:text-[#e2e8f0]"
                  >
                    {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                </div>
                {settings?.cloud.api_key && (
                  <p className="text-[10px] text-[#94a3b8]/60">当前: {settings.cloud.api_key}</p>
                )}
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#94a3b8]">模型名称</label>
                <input
                  value={cloudModel}
                  onChange={(e) => setCloudModel(e.target.value)}
                  placeholder="deepseek-chat"
                  className="glass-input w-full rounded-xl px-4 py-2.5 text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none"
                />
              </div>
              <motion.button
                className="neu-button flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-medium text-[#e2e8f0]"
                onClick={handleTestCloud}
                disabled={testing === "cloud"}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                {testing === "cloud" ? <Loader2 className="h-3 w-3 animate-spin text-indigo-400" /> : <Zap className="h-3 w-3 text-indigo-400" />}
                测试连接
              </motion.button>
              {cloudTestResult && (
                <div className={`rounded-xl p-2.5 text-xs flex items-center gap-2 ${cloudTestResult.ok ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>
                  {cloudTestResult.ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                  {cloudTestResult.msg}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Balance model config */}
        <AnimatePresence>
          {provider === "balance" && (
            <motion.div
              className="glass-card rounded-2xl p-5 space-y-3"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ type: "spring", stiffness: 200, damping: 25 }}
            >
              <h3 className="text-sm font-semibold text-[#e2e8f0]">余额模型</h3>
              <div className="rounded-xl neu-inset p-3 text-xs text-[#94a3b8]">
                使用平台提供的 API 额度，按量从账号余额扣费
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#94a3b8]">当前模型</span>
                <span className="font-mono text-xs text-[#e2e8f0]">{settings?.balance.model || "-"}</span>
              </div>
              <p className="text-[10px] text-[#94a3b8]/60">余额模型由管理员统一配置，如需修改请联系管理员</p>
              <div className="pt-3 border-t border-white/5">
                <div className="flex items-center justify-between rounded-xl neu-inset px-4 py-2.5">
                  <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
                    <CreditCard className="h-3.5 w-3.5" />
                    当前余额
                  </div>
                  <span className={`text-sm font-medium ${balance !== null && balance <= 0 ? "text-red-400" : "text-[#e2e8f0]"}`}>
                    {balance !== null ? `\u00a5 ${balance.toFixed(2)}` : "-"}
                  </span>
                </div>
                <p className="text-[10px] text-[#94a3b8]/60 mt-1 text-center">每次调用自动扣费，余额不足时请联系管理员充值</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Local model info */}
        <AnimatePresence>
          {provider === "local" && settings && (
            <motion.div
              className="glass-card rounded-2xl p-5 space-y-3"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ type: "spring", stiffness: 200, damping: 25 }}
            >
              <h3 className="text-sm font-semibold text-[#e2e8f0]">本地模型信息</h3>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#94a3b8]">服务地址</span>
                <span className="font-mono text-xs text-[#e2e8f0]">{settings.local.base_url}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[#94a3b8]">模型</span>
                <span className="font-mono text-xs text-[#e2e8f0]">{settings.local.model}</span>
              </div>
              <div className="rounded-xl neu-inset p-3 text-xs text-[#94a3b8] mt-2">
                使用本地模型需要先安装并启动 Ollama 服务。如果 Ollama 不可用，系统会提示切换到云端模型。
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Display settings */}
        <motion.div
          className="glass-card rounded-2xl p-5"
          variants={sectionVariants}
          initial="hidden"
          animate="show"
          transition={{ delay: 0.2 }}
        >
          <h3 className="text-sm font-semibold text-[#e2e8f0] flex items-center gap-2 mb-3">
            <Bot className="h-4 w-4 text-indigo-400" />
            显示设置
          </h3>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <p className="text-sm text-[#e2e8f0]">Agent 思考链可视化</p>
              <p className="text-[11px] text-[#94a3b8]">开启后，Agent 模式对话将实时展示工具调用过程（适用于答辩演示）</p>
            </div>
            <Toggle checked={agentVisualization} onChange={toggleAgentVisualization} />
          </div>
        </motion.div>

        {/* Background theme */}
        {bgThemes && (
          <motion.div
            className="glass-card rounded-2xl p-5 space-y-3"
            variants={sectionVariants}
            initial="hidden"
            animate="show"
            transition={{ delay: 0.25 }}
          >
            <h3 className="text-sm font-semibold text-[#e2e8f0] flex items-center gap-2">
              <Palette className="h-4 w-4 text-indigo-400" />
              背景主题
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {bgThemes.map((theme) => (
                <motion.button
                  key={theme.id}
                  onClick={() => onBgChange?.(theme.id)}
                  className={`relative rounded-xl p-3 text-xs font-medium transition-all ${
                    bgTheme === theme.id && !bgImage
                      ? "glass-card glow-border border-indigo-400/30"
                      : "neu-button"
                  }`}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                >
                  <div className={`h-8 w-full rounded-lg ${theme.className} mb-1.5`} />
                  <span className="text-[#94a3b8]">{theme.label}</span>
                  {bgTheme === theme.id && !bgImage && (
                    <motion.div
                      className="absolute top-1.5 right-1.5"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 500, damping: 25 }}
                    >
                      <Check className="h-3 w-3 text-indigo-400" />
                    </motion.div>
                  )}
                </motion.button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <div className="h-px flex-1 bg-white/5" />
              <span className="text-[10px] text-[#94a3b8]">或</span>
              <div className="h-px flex-1 bg-white/5" />
            </div>
            <label className="flex items-center justify-center gap-2 rounded-xl border-2 border-dashed border-white/10 p-3 text-xs text-[#94a3b8] hover:border-indigo-400/30 hover:text-[#e2e8f0] transition-colors cursor-pointer">
              <Upload className="h-4 w-4" />
              上传自定义背景图片
              <input type="file" accept="image/*" className="hidden" onChange={onBgImageUpload} />
            </label>
            {bgImage && (
              <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
                <Image className="h-3.5 w-3.5" />
                <span>已使用自定义背景</span>
                <button onClick={() => onBgChange?.("default")} className="ml-auto text-xs text-red-400 hover:underline">清除</button>
              </div>
            )}
          </motion.div>
        )}

        {/* Admin: Balance OCR config */}
        <AnimatePresence>
          {isAdmin && (
            <motion.div
              className="glass-card rounded-2xl p-5 border border-amber-500/20 space-y-3"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ delay: 0.3 }}
            >
              <h3 className="text-sm font-semibold text-[#e2e8f0] flex items-center gap-2">
                <Coins className="h-4 w-4 text-amber-400" />
                管理员 · 余额 OCR 配置
                <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20">仅管理员可见</span>
              </h3>
              <div className="rounded-xl neu-inset p-3 text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[#94a3b8]">配置状态</span>
                  {ocrConfigured ? (
                    <span className="flex items-center gap-1 text-emerald-400"><Check className="h-3 w-3" /> 已配置</span>
                  ) : (
                    <span className="flex items-center gap-1 text-amber-400"><X className="h-3 w-3" /> 未配置</span>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#94a3b8]">OCR 服务</span>
                  <span className="font-mono text-[10px] text-[#e2e8f0]">PaddleOCR-VL-1.6</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#94a3b8]">计费</span>
                  <span className="text-[10px] text-[#e2e8f0]">\u00a50.005 / 页</span>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#94a3b8]">PaddleOCR-VL Access Token</label>
                <div className="relative">
                  <input
                    type={showBalanceOcrKey ? "text" : "password"}
                    value={balanceOcrKey}
                    onChange={(e) => setBalanceOcrKey(e.target.value)}
                    placeholder="粘贴 PaddleOCR-VL API Token"
                    className="glass-input w-full rounded-xl px-4 py-2.5 text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none pr-10"
                  />
                  <button type="button" onClick={() => setShowBalanceOcrKey(!showBalanceOcrKey)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94a3b8] hover:text-[#e2e8f0]">
                    {showBalanceOcrKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                </div>
                <p className="text-[10px] text-[#94a3b8]/60">API 地址固定为 paddleocr.aistudio-app.com，只需填写 Access Token</p>
              </div>
              <div className="flex gap-2">
                <motion.button className="neu-button flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-medium text-[#e2e8f0]" onClick={handleSaveBalanceOcr} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                  <Save className="h-3 w-3 text-indigo-400" /> 保存
                </motion.button>
                <motion.button className="neu-button flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-medium text-[#e2e8f0]" onClick={handleTestOcr} disabled={testing === "ocr"} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                  {testing === "ocr" ? <Loader2 className="h-3 w-3 animate-spin text-indigo-400" /> : <Zap className="h-3 w-3 text-indigo-400" />}
                  测试连接
                </motion.button>
              </div>
              {ocrTestResult && (
                <div className={`rounded-xl p-2.5 text-xs flex items-center gap-2 ${ocrTestResult.ok ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>
                  {ocrTestResult.ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                  {ocrTestResult.msg}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Admin: Balance model config */}
        <AnimatePresence>
          {isAdmin && (
            <motion.div
              className="glass-card rounded-2xl p-5 border border-amber-500/20 space-y-3"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ delay: 0.35 }}
            >
              <h3 className="text-sm font-semibold text-[#e2e8f0] flex items-center gap-2">
                <Coins className="h-4 w-4 text-amber-400" />
                管理员 · 余额模型配置
                <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20">仅管理员可见</span>
              </h3>
              <div className="rounded-xl neu-inset p-3 text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[#94a3b8]">配置状态</span>
                  {adminBalanceUrl && adminBalanceModel ? (
                    <span className="flex items-center gap-1 text-emerald-400"><Check className="h-3 w-3" /> 已配置</span>
                  ) : (
                    <span className="flex items-center gap-1 text-amber-400"><X className="h-3 w-3" /> 未配置</span>
                  )}
                </div>
                {adminBalanceModel && (
                  <div className="flex items-center justify-between">
                    <span className="text-[#94a3b8]">模型</span>
                    <span className="font-mono text-[10px] text-[#e2e8f0]">{adminBalanceModel}</span>
                  </div>
                )}
                {adminBalanceUrl && (
                  <div className="flex items-center justify-between">
                    <span className="text-[#94a3b8]">API 地址</span>
                    <span className="font-mono text-[10px] text-[#e2e8f0]">{adminBalanceUrl}</span>
                  </div>
                )}
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#94a3b8]">API Base URL</label>
                <input value={adminBalanceUrl} onChange={(e) => setAdminBalanceUrl(e.target.value)} placeholder="https://api.deepseek.com/v1" className="glass-input w-full rounded-xl px-4 py-2.5 text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#94a3b8]">API Key</label>
                <div className="relative">
                  <input type={showAdminBalanceKey ? "text" : "password"} value={adminBalanceKey} onChange={(e) => setAdminBalanceKey(e.target.value)} placeholder="留空保持不变" className="glass-input w-full rounded-xl px-4 py-2.5 text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none pr-10" />
                  <button type="button" onClick={() => setShowAdminBalanceKey(!showAdminBalanceKey)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94a3b8] hover:text-[#e2e8f0]">
                    {showAdminBalanceKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-[#94a3b8]">模型名称</label>
                <input value={adminBalanceModel} onChange={(e) => setAdminBalanceModel(e.target.value)} placeholder="deepseek-chat" className="glass-input w-full rounded-xl px-4 py-2.5 text-xs text-[#e2e8f0] placeholder:text-[#94a3b8]/40 outline-none" />
              </div>
              <div className="flex gap-2">
                <motion.button className="neu-button flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-medium text-[#e2e8f0]" onClick={handleSaveBalanceModel} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                  <Save className="h-3 w-3 text-indigo-400" /> 保存
                </motion.button>
                <motion.button className="neu-button flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-medium text-[#e2e8f0]" onClick={handleTestBalanceModel} disabled={testing === "model"} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                  {testing === "model" ? <Loader2 className="h-3 w-3 animate-spin text-indigo-400" /> : <Zap className="h-3 w-3 text-indigo-400" />}
                  测试连接
                </motion.button>
              </div>
              {modelTestResult && (
                <div className={`rounded-xl p-2.5 text-xs flex items-center gap-2 ${modelTestResult.ok ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>
                  {modelTestResult.ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                  {modelTestResult.msg}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Save button */}
        <motion.div
          className="flex items-center gap-3"
          variants={sectionVariants}
          initial="hidden"
          animate="show"
          transition={{ delay: 0.4 }}
        >
          <motion.button
            onClick={handleSave}
            disabled={isSaving}
            className="flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium text-white bg-gradient-to-r from-indigo-500 to-violet-500 shadow-[0_0_20px_rgba(99,102,241,0.25)] hover:shadow-[0_0_30px_rgba(99,102,241,0.35)] transition-shadow disabled:opacity-50"
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
          >
            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            保存设置
          </motion.button>
          <AnimatePresence>
            {saveMsg && (
              <motion.span
                className={`text-xs ${saveMsg.includes("失败") ? "text-red-400" : "text-emerald-400"}`}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
              >
                {saveMsg}
              </motion.span>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  );
}
