"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Save, Check, Server, Cloud, CreditCard, Eye, EyeOff } from "lucide-react";
import type { LlmSettings } from "@/lib/types";
import * as api from "@/lib/api";

export function SettingsPanel() {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  // 编辑状态
  const [provider, setProvider] = useState<"local" | "cloud">("local");
  const [cloudUrl, setCloudUrl] = useState("");
  const [cloudKey, setCloudKey] = useState("");
  const [cloudModel, setCloudModel] = useState("");
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    api.getLlmSettings().then((res) => {
      setSettings(res);
      setProvider(res.provider);
      setCloudUrl(res.cloud.base_url);
      setCloudKey(""); // 不回填密钥
      setCloudModel(res.cloud.model);
    }).catch(() => {}).finally(() => setIsLoading(false));
  }, []);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    setSaveMsg("");
    try {
      const data: {
        provider: "local" | "cloud";
        cloud_base_url?: string;
        cloud_api_key?: string;
        cloud_model?: string;
      } = { provider };
      if (provider === "cloud") {
        data.cloud_base_url = cloudUrl;
        if (cloudKey) data.cloud_api_key = cloudKey;
        data.cloud_model = cloudModel;
      }
      await api.updateLlmSettings(data);
      setSaveMsg("保存成功，刷新后生效");
      setTimeout(() => setSaveMsg(""), 3000);
    } catch (e) {
      setSaveMsg("保存失败: " + (e as Error).message);
    } finally {
      setIsSaving(false);
    }
  }, [provider, cloudUrl, cloudKey, cloudModel]);

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

        {/* 模型提供商选择 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">模型提供商</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
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
                  OpenAI 兼容格式
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
                当前支持所有 OpenAI 兼容格式的 API 服务（DeepSeek、OpenAI、Moonshot 等）
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

              {/* 使用账号余额按钮 */}
              <div className="pt-2 border-t">
                <Button variant="outline" disabled className="w-full h-8 text-xs gap-2 opacity-60">
                  <CreditCard className="h-3.5 w-3.5" />
                  使用账号余额
                  <Badge variant="secondary" className="text-[10px] ml-auto">待开发</Badge>
                </Button>
                <p className="text-[10px] text-muted-foreground mt-1 text-center">
                  后续版本将支持账号余额直连，无需 API Key
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
