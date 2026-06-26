"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import * as api from "@/lib/api";
import { setToken, isAuthenticated } from "@/lib/auth";

// Particle configuration for background
const PARTICLES = Array.from({ length: 30 }, (_, i) => ({
  id: i,
  left: `${Math.random() * 100}%`,
  delay: Math.random() * 8,
  duration: 6 + Math.random() * 8,
  size: 1 + Math.random() * 2,
  opacity: 0.2 + Math.random() * 0.4,
}));

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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden aurora-bg">
      {/* CSS Particles background */}
      <div className="particles">
        {PARTICLES.map((p) => (
          <span
            key={p.id}
            style={{
              left: p.left,
              bottom: "-10px",
              width: `${p.size}px`,
              height: `${p.size}px`,
              opacity: p.opacity,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.duration}s`,
            }}
          />
        ))}
      </div>

      {/* Decorative gradient orbs */}
      <motion.div
        className="absolute -top-40 -left-40 h-96 w-96 rounded-full"
        style={{ background: "radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)" }}
        animate={{ x: [0, 30, 0], y: [0, -20, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full"
        style={{ background: "radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)" }}
        animate={{ x: [0, -30, 0], y: [0, 20, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute top-1/3 right-1/4 h-64 w-64 rounded-full"
        style={{ background: "radial-gradient(circle, rgba(236,72,153,0.08) 0%, transparent 70%)" }}
        animate={{ x: [0, 20, 0], y: [0, 30, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        className="relative z-10 w-full max-w-md px-4"
        initial={{ opacity: 0, scale: 0.9, y: 30 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        {/* Brand */}
        <motion.div
          className="mb-8 text-center"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          <h1 className="text-4xl font-bold tracking-tight text-white text-glow">
            智能学习助手
          </h1>
          <p className="mt-2 text-sm text-[#94a3b8] tracking-widest">
            AI-Powered Learning Assistant
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.5 }}
        >
          <Card className="glass-card glow-border border-0 rounded-2xl overflow-hidden">
            <CardHeader className="pb-4">
              <CardTitle className="text-xl text-white">
                <AnimatePresence mode="wait">
                  <motion.span
                    key={mode}
                    initial={{ opacity: 0, x: mode === "login" ? -20 : 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: mode === "login" ? 20 : -20 }}
                    transition={{ duration: 0.25 }}
                    className="block"
                  >
                    {mode === "login" ? "登录" : "注册"}
                  </motion.span>
                </AnimatePresence>
              </CardTitle>
              <CardDescription className="text-[#94a3b8]">
                <AnimatePresence mode="wait">
                  <motion.span
                    key={mode + "-desc"}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="block"
                  >
                    {mode === "login" ? "请输入您的账号信息" : "创建一个新账号"}
                  </motion.span>
                </AnimatePresence>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <motion.div
                  className="space-y-2"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 }}
                >
                  <label className="text-sm font-medium text-[#94a3b8]">
                    用户名
                  </label>
                  <Input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="请输入用户名"
                    required
                    autoFocus
                    className="glass-input h-11 rounded-xl border-0 text-white placeholder:text-[#64748b] focus-visible:ring-0 focus-visible:ring-offset-0"
                  />
                </motion.div>

                <motion.div
                  className="space-y-2"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.45 }}
                >
                  <label className="text-sm font-medium text-[#94a3b8]">
                    密码
                  </label>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === "register" ? "至少 6 位" : "请输入密码"}
                    required
                    className="glass-input h-11 rounded-xl border-0 text-white placeholder:text-[#64748b] focus-visible:ring-0 focus-visible:ring-offset-0"
                  />
                </motion.div>

                <AnimatePresence>
                  {mode === "register" && (
                    <motion.div
                      className="space-y-2"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.3, ease: "easeInOut" }}
                    >
                      <label className="text-sm font-medium text-[#94a3b8]">
                        确认密码
                      </label>
                      <Input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="请再次输入密码"
                        required
                        className="glass-input h-11 rounded-xl border-0 text-white placeholder:text-[#64748b] focus-visible:ring-0 focus-visible:ring-offset-0"
                      />
                    </motion.div>
                  )}
                </AnimatePresence>

                <AnimatePresence>
                  {error && (
                    <motion.div
                      className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-2.5"
                      initial={{ opacity: 0, y: -8, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -8, scale: 0.95 }}
                      transition={{ duration: 0.25 }}
                    >
                      <p className="text-sm text-red-400">{error}</p>
                    </motion.div>
                  )}
                </AnimatePresence>

                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 }}
                >
                  <Button
                    type="submit"
                    disabled={loading}
                    className="neu-button h-11 w-full rounded-xl border-0 text-white font-medium
                      bg-gradient-to-r from-[#6366f1] to-[#8b5cf6]
                      hover:from-[#7c7ff7] hover:to-[#9d75f8]
                      disabled:opacity-50 disabled:cursor-not-allowed
                      transition-all duration-300"
                  >
                    <AnimatePresence mode="wait">
                      <motion.span
                        key={loading ? "loading" : mode}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.2 }}
                        className="block"
                      >
                        {loading
                          ? (mode === "login" ? "登录中..." : "注册中...")
                          : (mode === "login" ? "登录" : "注册")
                        }
                      </motion.span>
                    </AnimatePresence>
                  </Button>
                </motion.div>

                <motion.p
                  className="text-center text-sm text-[#94a3b8]"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.55 }}
                >
                  {mode === "login" ? "还没有账号？" : "已有账号？"}
                  <button
                    type="button"
                    onClick={switchMode}
                    className="ml-1 text-[#818cf8] hover:text-[#a5b4fc] transition-colors duration-200"
                  >
                    {mode === "login" ? "立即注册" : "去登录"}
                  </button>
                </motion.p>
              </form>
            </CardContent>
          </Card>
        </motion.div>

        <motion.p
          className="mt-6 text-center text-xs text-[#64748b]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
        >
          Learning Assistant v0.2.0
        </motion.p>
      </motion.div>
    </div>
  );
}
