import { useState, useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Download, Pause, Play, X } from "lucide-react";

const DEFAULT_AI_PACK_API =
  (import.meta as any).env?.VITE_AI_PACK_API_URL ?? "http://192.168.1.34:8765";

type DownloadStatus = "idle" | "downloading" | "paused" | "extracting" | "done" | "error";

interface ProgressPayload {
  downloaded: number;
  total: number;
  percent: number;
}

interface ExtractProgressPayload {
  current: number;
  total: number;
  percent: number;
}

interface AIPackBannerProps {
  initialAiPackInstalled?: boolean | null;
}

export function AIPackBanner({ initialAiPackInstalled = null }: AIPackBannerProps) {
  const [installed, setInstalled] = useState<boolean | null>(initialAiPackInstalled ?? null);
  const [apiUrl, setApiUrl] = useState<string>(DEFAULT_AI_PACK_API);
  const [status, setStatus] = useState<DownloadStatus>("idle");
  const [progress, setProgress] = useState<ProgressPayload>({
    downloaded: 0,
    total: 0,
    percent: 0,
  });
  const [extractProgress, setExtractProgress] = useState<ExtractProgressPayload>({
    current: 0,
    total: 0,
    percent: 0,
  });
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (initialAiPackInstalled !== null) {
      setInstalled(initialAiPackInstalled);
      return;
    }
    let cancelled = false;
    invoke<boolean>("check_ai_pack_installed")
      .then((ok) => {
        if (!cancelled) setInstalled(ok);
      })
      .catch(() => {
        if (!cancelled) setInstalled(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialAiPackInstalled, status === "done"]);

  useEffect(() => {
    const unsubs: (() => void)[] = [];
    let cancelled = false;

    const setup = async () => {
      let u = await listen<ProgressPayload>("ai-pack-progress", (e) => {
        if (!cancelled) setProgress(e.payload);
      });
      unsubs.push(u);

      u = await listen("ai-pack-paused", () => {
        if (!cancelled) setStatus("paused");
      });
      unsubs.push(u);

      u = await listen<{ total: number }>("ai-pack-extracting", (e) => {
        if (!cancelled) {
          setStatus("extracting");
          setExtractProgress({ current: 0, total: e.payload?.total ?? 0, percent: 0 });
        }
      });
      unsubs.push(u);

      u = await listen<ExtractProgressPayload>("ai-pack-extract-progress", (e) => {
        if (!cancelled) setExtractProgress(e.payload);
      });
      unsubs.push(u);

      u = await listen("ai-pack-done", () => {
        if (!cancelled) {
          setStatus("done");
          setErrorMsg(null);
          invoke<boolean>("check_ai_pack_installed").then((ok) => setInstalled(ok));
        }
      });
      unsubs.push(u);

      u = await listen<{ message?: string }>("ai-pack-log", (e) => {
        if (!cancelled) {
          const msg = e.payload?.message ?? (typeof e.payload === "string" ? e.payload : JSON.stringify(e.payload));
          setLogLines((prev) => [...prev, msg]);
        }
      });
      unsubs.push(u);

      u = await listen<string>("ai-pack-error", (e) => {
        if (!cancelled) {
          setStatus("error");
          setErrorMsg(e.payload ?? "Download gagal");
        }
      });
      unsubs.push(u);
    };
    setup();
    return () => {
      cancelled = true;
      unsubs.forEach((f) => f());
    };
  }, []);

  const startDownload = () => {
    setErrorMsg(null);
    setLogLines([]);
    setStatus("downloading");
    invoke("start_download_ai_pack", {
      // Tauri v2: parameter Rust `base_url` diekspos ke JS sebagai `baseUrl`
      // Di-hardcode sesuai nilai default / Postman collection jika user tidak mengubah input.
      baseUrl: (apiUrl || DEFAULT_AI_PACK_API).trim(),
    }).catch((e) => {
      setStatus("error");
      setErrorMsg(String(e));
    });
  };

  const pauseDownload = () => {
    invoke("pause_download_ai_pack");
  };

  if (installed === true || dismissed) return null;

  const sizeMb =
    progress.total > 0
      ? `${(progress.downloaded / 1024 / 1024).toFixed(1)} / ${(progress.total / 1024 / 1024).toFixed(1)} MB`
      : "";

  return (
    <Card className="mx-4 mt-4 border-amber-500/50 bg-amber-500/5">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            AI pack belum terpasang — download untuk mengaktifkan inference
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setDismissed(true)}
            aria-label="Tutup"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1">
            <Label htmlFor="ai-pack-api">URL API AI pack</Label>
            <Input
              id="ai-pack-api"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder={DEFAULT_AI_PACK_API}
              disabled={status === "downloading"}
              className="font-mono text-sm"
            />
          </div>
          {status === "idle" || status === "error" ? (
            <Button onClick={startDownload} disabled={!apiUrl.trim()}>
              <Download className="mr-2 h-4 w-4" />
              Download
            </Button>
          ) : status === "downloading" ? (
            <Button variant="secondary" onClick={pauseDownload}>
              <Pause className="mr-2 h-4 w-4" />
              Jeda
            </Button>
          ) : status === "paused" ? (
            <Button onClick={startDownload}>
              <Play className="mr-2 h-4 w-4" />
              Lanjutkan
            </Button>
          ) : status === "extracting" ? null : null}
        </div>
        {(status === "downloading" || status === "paused") && (
          <div className="space-y-1">
            <Progress value={progress.percent} className="h-2" />
            <p className="text-xs text-muted-foreground">
              {progress.percent}% {sizeMb && ` — ${sizeMb}`}
            </p>
          </div>
        )}
        {status === "extracting" && (
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">
              Mengekstrak file ke folder binaries…
            </p>
            <Progress
              value={extractProgress.total > 0 ? extractProgress.percent : undefined}
              className="h-2"
            />
            <p className="text-xs text-muted-foreground">
              {extractProgress.total > 0
                ? `${extractProgress.current} / ${extractProgress.total} file`
                : "Memproses…"}
            </p>
          </div>
        )}
        {status === "done" && (
          <p className="text-sm text-green-600 dark:text-green-400">
            AI pack berhasil dipasang. Fitur inference siap dipakai.
          </p>
        )}
        {status === "error" && errorMsg && (
          <div className="space-y-2">
            <p className="text-sm text-destructive">{errorMsg}</p>
            {logLines.length > 0 && (
              <details className="text-xs">
                <summary className="cursor-pointer text-muted-foreground hover:underline">
                  Log lengkap ({logLines.length} baris)
                </summary>
                <pre className="mt-1 max-h-32 overflow-auto rounded border bg-muted/50 p-2 font-mono text-muted-foreground">
                  {logLines.join("\n")}
                </pre>
              </details>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
