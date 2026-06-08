"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import * as api from "@/lib/api";
import { setToken, isAuthenticated } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated()) {
      router.replace("/");
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        if (password !== confirmPassword) {
          setError("两次输入的密码不一致");
          setLoading(false);
          return;
        }
        const res = await api.register(username, password);
        setToken(res.token, res.username, res.role || 1);
      } else {
        const res = await api.login(username, password);
        setToken(res.token, res.username, res.role || 1);
      }
      router.push("/");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "操作失败";
      if (msg.includes("封禁") || msg.includes("403")) {
        setError("账号已被封禁，请联系管理员");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    const newMode = mode === "login" ? "register" : "login";
    setMode(newMode);
    setError("");
    setConfirmPassword("");
    // 切换到注册模式时检查注册开关
    if (newMode === "register") {
      api.checkRegistrationOpen().then((res) => {
        if (!res.allow_registration) {
          setError("当前未开放注册，请联系管理员");
          setMode("login");
        }
      }).catch(() => {});
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Subtle background pattern */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `radial-gradient(circle at 1px 1px, white 1px, transparent 0)`,
        backgroundSize: "40px 40px",
      }} />

      {/* Gradient orbs */}
      <div className="absolute -top-40 -left-40 h-80 w-80 rounded-full bg-blue-500/10 blur-3xl" />
      <div className="absolute -bottom-40 -right-40 h-80 w-80 rounded-full bg-purple-500/10 blur-3xl" />

      <div className="relative z-10 w-full max-w-md px-4">
        {/* Brand */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-white">
            智能学习助手
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            AI-Powered Learning Assistant
          </p>
        </div>

        <Card className="border-slate-700/50 bg-slate-800/80 shadow-2xl backdrop-blur-xl">
          <CardHeader className="pb-4">
            <CardTitle className="text-xl text-white">
              {mode === "login" ? "登录" : "注册"}
            </CardTitle>
            <CardDescription className="text-slate-400">
              {mode === "login" ? "请输入您的账号信息" : "创建一个新账号"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-300">
                  用户名
                </label>
                <Input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入用户名"
                  required
                  autoFocus
                  className="h-10 border-slate-600 bg-slate-700/50 text-white placeholder:text-slate-500 focus:border-blue-500 focus:ring-blue-500/20"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-300">
                  密码
                </label>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "register" ? "至少 6 位" : "请输入密码"}
                  required
                  className="h-10 border-slate-600 bg-slate-700/50 text-white placeholder:text-slate-500 focus:border-blue-500 focus:ring-blue-500/20"
                />
              </div>

              {mode === "register" && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-300">
                    确认密码
                  </label>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="请再次输入密码"
                    required
                    className="h-10 border-slate-600 bg-slate-700/50 text-white placeholder:text-slate-500 focus:border-blue-500 focus:ring-blue-500/20"
                  />
                </div>
              )}

              {error && (
                <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              <Button
                type="submit"
                disabled={loading}
                className="h-10 w-full bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {loading
                  ? (mode === "login" ? "登录中..." : "注册中...")
                  : (mode === "login" ? "登录" : "注册")
                }
              </Button>

              <p className="text-center text-sm text-slate-400">
                {mode === "login" ? "还没有账号？" : "已有账号？"}
                <button
                  type="button"
                  onClick={switchMode}
                  className="ml-1 text-blue-400 hover:text-blue-300 hover:underline"
                >
                  {mode === "login" ? "立即注册" : "去登录"}
                </button>
              </p>
            </form>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-slate-500">
          Learning Assistant v0.2.0
        </p>
      </div>
    </div>
  );
}
