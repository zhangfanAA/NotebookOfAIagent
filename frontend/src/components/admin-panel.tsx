"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Loader2, Users, CreditCard, Activity, Search,
  ChevronLeft, ChevronRight, Shield, User, Ban, Settings,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { UserInfo, UsageLog } from "@/lib/types";
import * as api from "@/lib/api";

export function AdminPanel() {
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold">用户管理</h1>
        </div>
        <Tabs defaultValue="users" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="users" className="gap-1.5">
              <Users className="h-3.5 w-3.5" /> 用户列表
            </TabsTrigger>
            <TabsTrigger value="logs" className="gap-1.5">
              <Activity className="h-3.5 w-3.5" /> 用量日志
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-1.5">
              <Settings className="h-3.5 w-3.5" /> 系统设置
            </TabsTrigger>
          </TabsList>
          <TabsContent value="users">
            <UsersTab />
          </TabsContent>
          <TabsContent value="logs">
            <LogsTab />
          </TabsContent>
          <TabsContent value="settings">
            <SettingsTab />
          </TabsContent>
        </Tabs>
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
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-red-500">{error}</CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">全部用户 ({users.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {/* Header row */}
            <div className="grid grid-cols-[2rem_1fr_80px_80px_100px_130px_130px_140px] gap-2 px-2 text-[10px] font-medium text-muted-foreground uppercase">
              <span>ID</span>
              <span>用户名</span>
              <span>角色</span>
              <span>状态</span>
              <span>余额</span>
              <span>最后上线</span>
              <span>注册时间</span>
              <span>操作</span>
            </div>
            {users.map((u) => (
              <div
                key={u.id}
                className={cn(
                  "grid grid-cols-[2rem_1fr_80px_80px_100px_130px_130px_140px] items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-muted/50",
                  u.banned === 1 && "opacity-60"
                )}
              >
                <span className="text-muted-foreground text-xs">{u.id}</span>
                <span className="flex items-center gap-1.5 font-medium truncate">
                  {u.role === 2 ? <Shield className="h-3.5 w-3.5 text-primary shrink-0" /> : <User className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                  {u.username}
                </span>
                <Badge variant={u.role === 2 ? "default" : "secondary"} className="w-fit text-[10px]">
                  {u.role === 2 ? "管理员" : "用户"}
                </Badge>
                <span>
                  {u.banned === 1 ? (
                    <Badge variant="destructive" className="w-fit text-[10px] gap-0.5">
                      <Ban className="h-2.5 w-2.5" /> 封禁
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="w-fit text-[10px] text-green-600">正常</Badge>
                  )}
                </span>
                <span className="font-mono text-xs">
                  <span className={u.balance <= 0 ? "text-red-500" : "text-green-600"}>
                    {u.balance.toFixed(2)}
                  </span>
                </span>
                <span className="text-xs text-muted-foreground">
                  {u.last_online_at
                    ? new Date(u.last_online_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
                    : "未登录"}
                </span>
                <span className="text-xs text-muted-foreground">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString("zh-CN") : "-"}
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs gap-1"
                    onClick={() => openAdjustDialog(u)}
                  >
                    <CreditCard className="h-3 w-3" />
                    调整
                  </Button>
                  {u.role !== 2 && (
                    <Button
                      variant={u.banned === 1 ? "outline" : "destructive"}
                      size="sm"
                      className="h-7 text-xs gap-1"
                      disabled={banning === u.id}
                      onClick={() => handleToggleBan(u.id, u.banned !== 1)}
                    >
                      {banning === u.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : u.banned === 1 ? (
                        "解封"
                      ) : (
                        <><Ban className="h-3 w-3" /> 封号</>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            ))}
            {users.length === 0 && (
              <p className="text-center text-sm text-muted-foreground py-8">暂无用户</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Balance adjustment dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>调整余额</DialogTitle>
            <DialogDescription>
              为 <span className="font-semibold text-foreground">{selectedUser?.username}</span> 调整余额
              （当前：<span className={cn("font-mono font-semibold", (selectedUser?.balance ?? 0) <= 0 ? "text-red-500" : "text-green-600")}>
                {selectedUser?.balance.toFixed(2)}
              </span> 元）
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <label className="text-sm font-medium">调整金额</label>
            <Input
              type="number"
              value={adjustAmount}
              onChange={(e) => setAdjustAmount(e.target.value)}
              placeholder="输入正数增加，负数扣减，如 10 或 -5"
              className="text-base h-11"
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleAdjustBalance()}
            />
            <div className="flex gap-2">
              {[10, 50, 100, 500].map((v) => (
                <Button
                  key={v}
                  variant="outline"
                  size="sm"
                  className="flex-1 h-8 text-xs"
                  onClick={() => setAdjustAmount(String(v))}
                >
                  +{v}
                </Button>
              ))}
            </div>
            <div className="flex gap-2">
              {[-10, -50, -100].map((v) => (
                <Button
                  key={v}
                  variant="outline"
                  size="sm"
                  className="flex-1 h-8 text-xs"
                  onClick={() => setAdjustAmount(String(v))}
                >
                  {v}
                </Button>
              ))}
              <div className="flex-1" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button
              onClick={handleAdjustBalance}
              disabled={adjusting || !adjustAmount || parseFloat(adjustAmount) === 0}
            >
              {adjusting && <Loader2 className="h-4 w-4 animate-spin mr-1.5" />}
              确认调整
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
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
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">用量日志 ({total})</CardTitle>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2 top-1.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="用户ID"
                value={filterUid}
                onChange={(e) => { setFilterUid(e.target.value); setPage(1); }}
                className="h-7 w-24 pl-7 text-xs"
              />
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            <div className="space-y-1">
              <div className="grid grid-cols-[2rem_3rem_1fr_80px_80px_80px_140px] gap-2 px-2 text-[10px] font-medium text-muted-foreground uppercase">
                <span>ID</span>
                <span>UID</span>
                <span>模型</span>
                <span>输入</span>
                <span>输出</span>
                <span>费用</span>
                <span>时间</span>
              </div>
              {logs.map((log) => (
                <div
                  key={log.id}
                  className="grid grid-cols-[2rem_3rem_1fr_80px_80px_80px_140px] gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-muted/50"
                >
                  <span className="text-muted-foreground">{log.id}</span>
                  <span className="text-muted-foreground">{log.user_id}</span>
                  <span className="truncate font-mono">{log.model}</span>
                  <span className="text-muted-foreground">{log.prompt_tokens.toLocaleString()}</span>
                  <span className="text-muted-foreground">{log.completion_tokens.toLocaleString()}</span>
                  <span className="font-mono">{log.cost.toFixed(4)}</span>
                  <span className="text-muted-foreground">
                    {new Date(log.created_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              ))}
              {logs.length === 0 && (
                <p className="text-center text-sm text-muted-foreground py-8">暂无日志</p>
              )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <span className="text-xs text-muted-foreground">
                  第 {page} / {totalPages} 页
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function SettingsTab() {
  const [allowRegistration, setAllowRegistration] = useState(true);
  const [paddleOcrEnabled, setPaddleOcrEnabled] = useState(true);
  const [gpuStatus, setGpuStatus] = useState<{ gpu_available: boolean; device: string; details?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getRegistrationSetting(),
      api.getPaddleOcrSetting(),
      api.getPaddleOcrGpuStatus(),
    ]).then(([regRes, paddleRes, gpuRes]) => {
      setAllowRegistration(regRes.allow_registration);
      setPaddleOcrEnabled(paddleRes.enabled);
      setGpuStatus(gpuRes);
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

  const handleTogglePaddleOcr = async () => {
    try {
      setSaving("paddle-ocr");
      const newValue = !paddleOcrEnabled;
      await api.updatePaddleOcrSetting(newValue);
      setPaddleOcrEnabled(newValue);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">系统设置</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 注册开关 */}
        <div className="flex items-center justify-between rounded-lg border p-4">
          <div className="space-y-0.5">
            <div className="text-sm font-medium">开放注册</div>
            <div className="text-xs text-muted-foreground">
              关闭后新用户将无法注册账号
            </div>
          </div>
          <button
            onClick={handleToggleRegistration}
            disabled={saving !== null}
            className={cn(
              "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
              allowRegistration ? "bg-primary" : "bg-muted-foreground/30",
              saving === "registration" && "opacity-50 cursor-not-allowed"
            )}
          >
            <span
              className={cn(
                "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform duration-200 ease-in-out",
                allowRegistration ? "translate-x-5" : "translate-x-0"
              )}
            />
          </button>
        </div>
        <div className="text-xs text-muted-foreground -mt-2">
          当前状态：{allowRegistration ? "已开放注册" : "注册已关闭"}
        </div>

        {/* PaddleOCR 开关 */}
        <div className="flex items-center justify-between rounded-lg border p-4">
          <div className="space-y-0.5">
            <div className="text-sm font-medium">启用 PaddleOCR</div>
            <div className="text-xs text-muted-foreground">
              启用后支持扫描型（图片）PDF 的文字识别，关闭则只支持文字型 PDF
            </div>
          </div>
          <button
            onClick={handleTogglePaddleOcr}
            disabled={saving !== null}
            className={cn(
              "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
              paddleOcrEnabled ? "bg-primary" : "bg-muted-foreground/30",
              saving === "paddle-ocr" && "opacity-50 cursor-not-allowed"
            )}
          >
            <span
              className={cn(
                "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform duration-200 ease-in-out",
                paddleOcrEnabled ? "translate-x-5" : "translate-x-0"
              )}
            />
          </button>
        </div>
        <div className="text-xs text-muted-foreground -mt-2 space-y-1">
          <div>当前状态：{paddleOcrEnabled ? "已启用（支持扫描型 PDF）" : "已禁用（仅支持文字型 PDF）"}</div>
          {gpuStatus && (
            <div className="flex items-center gap-1.5">
              <span>计算设备：</span>
              <Badge variant={gpuStatus.gpu_available ? "default" : "secondary"} className="text-[10px]">
                {gpuStatus.device}
              </Badge>
              {gpuStatus.details && (
                <span className="text-muted-foreground">({gpuStatus.details})</span>
              )}
              {gpuStatus.gpu_available && (
                <span className="text-green-600">✓ GPU 加速</span>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
