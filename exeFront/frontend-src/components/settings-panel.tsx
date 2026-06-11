"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Save, Check, Server, Cloud, CreditCard, Eye, EyeOff, Wallet, Coins, ScanLine } from "lucide-react";
import type { LlmSettings } from "@/lib/types";
import * as api from "@/lib/api";

export function SettingsPanel() {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  // 编辑状态
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
  const [ocrMode, setOcrMode] = useState<"local" | "cloud" | "server">(() => {
    if (typeof window === "undefined") return "local";
    return (localStorage.getItem("ocr_mode") as "local" | "cloud" | "server") || "local";
  });
  const [cloudOcrToken, setCloudOcrToken] = useState(() => api.getCloudOcrToken());
  const [showOcrToken, setShowOcrToken] = useState(false);

  useEffect(() => {
    api.getBalance().then((res) => setBalance(res.balance)).catch(() => {});
  }, []);

  useEffect(() => {
    api.getLlmSettings().then((res) => {
      setSettings(res);
      setProvider(res.provider);
      setCloudUrl(res.cloud.base_url);
      setCloudKey(""); // 不回填密钥
      setCloudModel(res.cloud.model);
      setBalanceUrl(res.balance.base_url);
      setBalanceKey(""); // 不回填密钥
      setBalanceModel(res.balance.model);
    }).catch(() => {}).finally(() => setIsLoading(false));
  }, []);

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
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold">⚙️ 设置</h1>

        {/* 账号余额 */}
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wallet className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">账号余额</span>
              </div>
              <span className={`text-lg font-semibold ${balance !== null && balance <= 0 ? "text-red-500" : ""}`}>
                {balance !== null ? `¥ ${balance.toFixed(2)}` : "-"}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* OCR 设置 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <ScanLine className="h-4 w-4" />
              OCR 文字识别
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-1">
              <Button
                variant={ocrMode === "local" ? "default" : "outline"}
                size="sm"
                className="flex-1 h-8 text-xs"
                onClick={() => { setOcrMode("local"); localStorage.setItem("ocr_mode", "local"); }}
              >
                本地 OCR
              </Button>
              <Button
                variant={ocrMode === "cloud" ? "default" : "outline"}
                size="sm"
                className="flex-1 h-8 text-xs"
                onClick={() => { setOcrMode("cloud"); localStorage.setItem("ocr_mode", "cloud"); }}
              >
                云端 OCR
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs opacity-50 cursor-not-allowed"
                disabled
              >
                服务器
                <Badge variant="secondary" className="ml-0.5 text-[8px] px-0.5 py-0">待开发</Badge>
              </Button>
            </div>
            {ocrMode === "cloud" && (
              <div className="space-y-1">
                <label className="text-xs font-medium">云端 OCR Token</label>
                <div className="relative">
                  <Input
                    type={showOcrToken ? "text" : "password"}
                    value={cloudOcrToken}
                    onChange={(e) => { setCloudOcrToken(e.target.value); api.setCloudOcrToken(api.extractBearerToken(e.target.value)); }}
                    placeholder="粘贴 Bearer Token 或 API Key"
                    className="h-8 text-xs pr-8"
                  />
                  <button
                    type="button"
                    onClick={() => setShowOcrToken(!showOcrToken)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showOcrToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  用于扫描型 PDF 的文字识别，支持 PaddleOCR-VL 云端 API
                </p>
              </div>
            )}
            {ocrMode === "local" && (
              <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
                使用本地 PaddleOCR 引擎识别扫描型 PDF，需要安装 PaddleOCR
              </div>
            )}
            {ocrMode === "server" && (
              <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
                服务器 OCR 功能开发中，敬请期待
              </div>
            )}
          </CardContent>
        </Card>

        {/* 模型提供商选择 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">模型提供商</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3">
              {/* 本地模型 */}
              <button
                onClick={() => setProvider("local")}
                className={`relative rounded-xl border-2 p-4 text-left transition-all ${
                  provider === "local"
                    ? "border-primary bg-primary/5"
                    : "border-muted hover:border-muted-foreground/30"
                }`}
              >
                {provider === "local" && (
                  <div className="absolute top-2 right-2">
                    <Check className="h-4 w-4 text-primary" />
                  </div>
                )}
                <Server className="h-6 w-6 mb-2 text-muted-foreground" />
                <p className="text-sm font-medium">本地模型</p>
                <p className="text-[10px] text-muted-foreground mt-1">Ollama</p>
                {settings && (
                  <div className="mt-2 space-y-0.5">
                    <p className="text-[10px] text-muted-foreground truncate">
                      模型: {settings.local.model}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      地址: {settings.local.base_url}
                    </p>
                  </div>
                )}
              </button>

              {/* 云端模型 */}
              <button
                onClick={() => setProvider("cloud")}
                className={`relative rounded-xl border-2 p-4 text-left transition-all ${
                  provider === "cloud"
                    ? "border-primary bg-primary/5"
                    : "border-muted hover:border-muted-foreground/30"
                }`}
              >
                {provider === "cloud" && (
                  <div className="absolute top-2 right-2">
                    <Check className="h-4 w-4 text-primary" />
                  </div>
                )}
                <Cloud className="h-6 w-6 mb-2 text-muted-foreground" />
                <p className="text-sm font-medium">云端模型</p>
                <Badge variant="outline" className="mt-1 text-[10px]">
                  自备 Key
                </Badge>
              </button>

              {/* 余额模型 */}
              <button
                onClick={() => setProvider("balance")}
                className={`relative rounded-xl border-2 p-4 text-left transition-all ${
                  provider === "balance"
                    ? "border-primary bg-primary/5"
                    : "border-muted hover:border-muted-foreground/30"
                }`}
              >
                {provider === "balance" && (
                  <div className="absolute top-2 right-2">
                    <Check className="h-4 w-4 text-primary" />
                  </div>
                )}
                <Coins className="h-6 w-6 mb-2 text-muted-foreground" />
                <p className="text-sm font-medium">余额模型</p>
                <Badge variant="outline" className="mt-1 text-[10px]">
                  按量扣费
                </Badge>
              </button>
            </div>
          </CardContent>
        </Card>

        {/* 云端配置 */}
        {provider === "cloud" && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">云端 API 配置</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
                自备 API Key，支持所有 OpenAI 兼容格式（DeepSeek、OpenAI、Moonshot 等）
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium">API Base URL</label>
                <Input
                  value={cloudUrl}
                  onChange={(e) => setCloudUrl(e.target.value)}
                  placeholder="https://api.deepseek.com/v1"
                  className="h-8 text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium">API Key</label>
                <div className="relative">
                  <Input
                    type={showKey ? "text" : "password"}
                    value={cloudKey}
                    onChange={(e) => setCloudKey(e.target.value)}
                    placeholder={settings?.cloud.api_key ? "已配置（留空保持不变）" : "sk-..."}
                    className="h-8 text-xs pr-8"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                </div>
                {settings?.cloud.api_key && (
                  <p className="text-[10px] text-muted-foreground">
                    当前: {settings.cloud.api_key}
                  </p>
                )}
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium">模型名称</label>
                <Input
                  value={cloudModel}
                  onChange={(e) => setCloudModel(e.target.value)}
                  placeholder="deepseek-chat"
                  className="h-8 text-xs"
                />
              </div>
            </CardContent>
          </Card>
        )}

        {/* 余额模型配置 */}
        {provider === "balance" && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">余额模型</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
                使用平台提供的 API 额度，按量从账号余额扣费
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">当前模型</span>
                <span className="font-mono text-xs">{settings?.balance.model || "-"}</span>
              </div>

              <p className="text-[10px] text-muted-foreground">
                余额模型由管理员统一配置，如需修改请联系管理员
              </p>

              {/* 余额信息 */}
              <div className="pt-2 border-t">
                <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <CreditCard className="h-3.5 w-3.5" />
                    当前余额
                  </div>
                  <span className={`text-sm font-medium ${balance !== null && balance <= 0 ? "text-red-500" : ""}`}>
                    {balance !== null ? `¥ ${balance.toFixed(2)}` : "-"}
                  </span>
                </div>
                <p className="text-[10px] text-muted-foreground mt-1 text-center">
                  每次调用自动扣费，余额不足时请联系管理员充值
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* 本地模型信息 */}
        {provider === "local" && settings && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">本地模型信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">服务地址</span>
                <span className="font-mono text-xs">{settings.local.base_url}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">模型</span>
                <span className="font-mono text-xs">{settings.local.model}</span>
              </div>
              <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground mt-2">
                使用本地模型需要先安装并启动 Ollama 服务。
                如果 Ollama 不可用，系统会提示切换到云端模型。
              </div>
            </CardContent>
          </Card>
        )}

        {/* 保存按钮 */}
        <div className="flex items-center gap-3">
          <Button onClick={handleSave} disabled={isSaving} className="flex-1 h-9">
            {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
            保存设置
          </Button>
          {saveMsg && (
            <span className={`text-xs ${saveMsg.includes("失败") ? "text-red-500" : "text-green-500"}`}>
              {saveMsg}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
