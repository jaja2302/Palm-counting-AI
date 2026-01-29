import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AIPackBanner } from "@/components/AIPackBanner";
import { Dashboard, YoloModelPage, SettingsPage } from "@/pages";
import { useConversionStore } from "@/stores/conversion";
import {
  useProcessingStore,
  type ProcessingProgress,
} from "@/stores/processing";
import { applyTheme, useThemeStore, type Theme } from "@/stores/theme";
import { Sun, Moon, Monitor, Loader2 } from "lucide-react";

interface DonePayload {
  successful: number;
  failed: number;
  total: number;
  total_abnormal: number;
  total_normal: number;
}

async function sendProcessingDoneNotification(p: DonePayload) {
  let granted = await isPermissionGranted();
  if (!granted) {
    const perm = await requestPermission();
    granted = perm === "granted";
  }
  if (!granted) return;
  let body: string;
  if (p.total === 0) {
    body = "Processing selesai.";
  } else {
    const parts: string[] = [];
    if (p.successful > 0) parts.push(`${p.successful} berhasil`);
    if (p.failed > 0) parts.push(`${p.failed} gagal`);
    const summary = parts.length ? parts.join(", ") + "." : "Selesai.";
    const counts =
      p.total_abnormal > 0 || p.total_normal > 0
        ? ` Abnormal: ${p.total_abnormal}, Normal: ${p.total_normal}.`
        : "";
    body = `${summary} ${counts}`.trim();
  }
  sendNotification({ title: "Palm Counting AI", body });
}

function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  const icon =
    theme === "dark" ? (
      <Moon className="h-4 w-4" />
    ) : theme === "light" ? (
      <Sun className="h-4 w-4" />
    ) : (
      <Monitor className="h-4 w-4" />
    );

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9"
          aria-label="Theme (Light / Dark / System)"
          title="Theme: Light, Dark, System"
        >
          {icon}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        side="bottom"
        sideOffset={6}
        className="w-44 z-100"
        avoidCollisions
      >
        <DropdownMenuRadioGroup
          value={theme}
          onValueChange={(v) => setTheme(v as Theme)}
        >
          <DropdownMenuRadioItem value="light">
            <Sun className="mr-2 h-4 w-4" />
            Light
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark">
            <Moon className="mr-2 h-4 w-4" />
            Dark
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system">
            <Monitor className="mr-2 h-4 w-4" />
            System
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ProcessingStrip() {
  const running = useProcessingStore((s) => s.running);
  const progress = useProcessingStore((s) => s.progress);
  const log = useProcessingStore((s) => s.log);
  const clearLog = useProcessingStore((s) => s.clearLog);
  const cancel = useProcessingStore((s) => s.cancel);

  const hasLog = log.length > 0;
  if (!running && !hasLog) return null;

  return (
    <div className="border-t bg-muted/30 space-y-4 p-4">
      {running && (
        <>
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm font-medium">Processing…</span>
            <Button variant="destructive" size="sm" onClick={cancel}>
              Cancel
            </Button>
          </div>
          {progress && (
            <Card className="border-border/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Progress</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Progress value={progress.total ? (progress.processed / progress.total) * 100 : 0} />
                <p className="text-sm">
                  {progress.processed} / {progress.total} —{" "}
                  {progress.current_file?.split(/[/\\]/).pop() ?? progress.current_file}{" "}
                  — {progress.status}
                </p>
                <p className="text-sm text-muted-foreground">
                  Abnormal: {progress.abnormal_count} — Normal:{" "}
                  {progress.normal_count}
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}
      {hasLog && (
        <Card className="border-border/50">
          <CardHeader className="flex flex-row items-center justify-between py-2">
            <CardTitle className="text-base">
              {running ? "Log" : "Log (selesai)"}
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={clearLog}>
              Clear
            </Button>
          </CardHeader>
          <CardContent className="py-2">
            <ScrollArea className="h-40 rounded-lg border border-border/50 bg-muted/20 p-2 font-mono text-xs">
              {log.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

const LOADING_DELAY_MS = 20_000; // 20 detik sebelum tampil dashboard

export default function App() {
  const [appReady, setAppReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const minEnd = Date.now() + LOADING_DELAY_MS;

    const run = async () => {
      const checks = Promise.all([
        invoke<boolean>("check_ai_pack_installed").catch(() => false),
        invoke<unknown[]>("list_models_cmd").catch(() => []),
      ]);
      await checks;
      if (cancelled) return;
      const elapsed = minEnd - Date.now();
      if (elapsed > 0) {
        await new Promise((r) => setTimeout(r, elapsed));
      }
      if (!cancelled) setAppReady(true);
    };
    run();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const unsubs: (() => void)[] = [];
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const setConversion = useConversionStore.getState().setStatus;

    const setup = async () => {
      let u = await listen<string>("model-conversion-start", (e) => {
        setConversion(e.payload, true);
      });
      if (cancelled) {
        u();
        return;
      }
      unsubs.push(u);

      u = await listen<string>("model-conversion-done", (e) => {
        setConversion(e.payload, false);
        if (timeoutId) clearTimeout(timeoutId);
        timeoutId = setTimeout(() => setConversion(null, false), 3000);
      });
      if (cancelled) {
        u();
        return;
      }
      unsubs.push(u);

      u = await listen<string>("model-conversion-error", (e) => {
        setConversion(`Error: ${e.payload}`, false);
        if (timeoutId) clearTimeout(timeoutId);
        timeoutId = setTimeout(() => setConversion(null, false), 5000);
      });
      if (cancelled) {
        u();
        return;
      }
      unsubs.push(u);
    };
    setup();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      unsubs.forEach((f) => f());
    };
  }, []);

  useEffect(() => {
    const unsubs: (() => void)[] = [];
    let cancelled = false;
    const appendLog = useProcessingStore.getState().appendLog;
    const setProgress = useProcessingStore.getState().setProgress;
    const setRunning = useProcessingStore.getState().setRunning;

    const setup = async () => {
      let u = await listen<string>("processing-log", (e) =>
        appendLog(e.payload)
      );
      if (cancelled) {
        u();
        return;
      }
      unsubs.push(u);

      u = await listen<ProcessingProgress>(
        "processing-progress",
        (e) => setProgress(e.payload)
      );
      if (cancelled) {
        u();
        return;
      }
      unsubs.push(u);

      u = await listen<DonePayload>("processing-done", (e) => {
        setRunning(false);
        sendProcessingDoneNotification(e.payload).catch(() => {});
      });
      if (cancelled) {
        u();
        return;
      }
      unsubs.push(u);
    };
    setup();

    return () => {
      cancelled = true;
      unsubs.forEach((f) => f());
    };
  }, []);

  useEffect(() => {
    const theme = useThemeStore.getState().theme;
    if (theme !== "system") return;
    const m = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    m.addEventListener("change", handler);
    return () => m.removeEventListener("change", handler);
  }, []);

  if (!appReady) {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center gap-6 p-6">
        <Loader2 className="h-12 w-12 animate-spin text-primary" aria-hidden />
        <div className="text-center space-y-2">
          <p className="text-lg font-medium">Memuat Palm Counting AI</p>
          <p className="text-sm text-muted-foreground">
            Mengecek model dan AI pack… Siap dalam ~20 detik.
          </p>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={300}>
      <div className="min-h-screen bg-background text-foreground flex flex-col">
        <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60">
          <div className="flex h-14 items-center justify-between px-4">
            <h1 className="text-lg font-semibold tracking-tight">
              Palm Counting AI
            </h1>
            <ThemeToggle />
          </div>
        </header>
        <AIPackBanner />
        <Tabs defaultValue="dashboard" className="flex flex-1 flex-col">
          <TabsList className="h-11 w-full justify-start gap-0 rounded-none border-b bg-transparent px-4 py-0">
            <TabsTrigger
              value="dashboard"
              className="rounded-none border-b-2 border-transparent px-6 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none"
            >
              Dashboard
            </TabsTrigger>
            <TabsTrigger
              value="yolo"
              className="rounded-none border-b-2 border-transparent px-6 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none"
            >
              YOLO Model
            </TabsTrigger>
            <TabsTrigger
              value="settings"
              className="rounded-none border-b-2 border-transparent px-6 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none"
            >
              Settings
            </TabsTrigger>
          </TabsList>
          <TabsContent value="dashboard" className="mt-0 flex-1 data-[state=inactive]:hidden">
            <Dashboard />
          </TabsContent>
          <TabsContent value="yolo" className="mt-0 flex-1 data-[state=inactive]:hidden">
            <YoloModelPage />
          </TabsContent>
          <TabsContent value="settings" className="mt-0 flex-1 data-[state=inactive]:hidden">
            <SettingsPage />
          </TabsContent>
        </Tabs>
        <ProcessingStrip />
        <footer className="mt-auto border-t bg-muted/30 px-4 py-3 text-center text-xs text-muted-foreground">
          © 2026–present Digital Architect. All rights reserved.
        </footer>
      </div>
    </TooltipProvider>
  );
}
