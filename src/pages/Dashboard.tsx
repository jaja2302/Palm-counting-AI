import { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";
import { listen } from "@tauri-apps/api/event";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Input } from "@/components/ui/input";
import { FolderOpen, Trash2, Plus, Play } from "lucide-react";
import { useProcessingStore } from "@/stores/processing";

interface SystemSpecs {
  os: string;
  processor: string;
  total_ram_gb: string;
  gpu: string;
  gpu_memory: string;
  cpu_cores: number;
  cpu_threads: number;
}

interface YoloModel {
  id: number;
  name: string;
  path: string;
  is_active: boolean;
}

interface AppConfig {
  imgsz?: string;
  iou?: string;
  conf?: string;
  device?: string;
  convert_kml?: string;
  convert_shp?: string;
  save_annotated?: string;
  last_folder_path?: string;
}

interface TiffEntry {
  path: string;
  checked: boolean;
}

interface TiffTfwGroup {
  name: string;
  tifPath: string;
  tfwPath: string;
}

function stem(p: string): string {
  const b = p.split(/[/\\]/).pop() ?? p;
  return b.replace(/\.(tif|tiff|tfw)$/i, "");
}

function normalizePathForLookup(p: string): string {
  return p.replace(/\//g, "\\").replace(/\\\\+/g, "\\").toLowerCase();
}

function getOutputFolder(
  tifPath: string,
  folders: Record<string, string>
): string | undefined {
  if (folders[tifPath]) return folders[tifPath];
  const n = normalizePathForLookup(tifPath);
  const e = Object.entries(folders).find(([k]) => normalizePathForLookup(k) === n);
  return e?.[1];
}

function parseTiffTfwPairs(paths: string[]): TiffTfwGroup[] {
  const groups = new Map<string, { tif?: string; tfw?: string }>();
  for (const p of paths) {
    const dir = p.replace(/[/\\][^/\\]*$/, "");
    const base = stem(p);
    const key = dir + "\0" + base;
    if (!groups.has(key)) groups.set(key, {});
    const g = groups.get(key)!;
    if (/\.(tif|tiff)$/i.test(p)) g.tif = p;
    else if (/\.tfw$/i.test(p)) g.tfw = p;
  }
  const out: TiffTfwGroup[] = [];
  for (const [, g] of groups) {
    if (g.tif && g.tfw)
      out.push({ name: stem(g.tif), tifPath: g.tif, tfwPath: g.tfw });
  }
  return out;
}

interface RealtimeUsage {
  cpu_percent: number;
  gpu_percent?: number;
  gpu_memory_used_mb?: number;
  gpu_memory_total_mb?: number;
  gpu_temp_c?: number;
}

export function Dashboard() {
  const running = useProcessingStore((s) => s.running);
  const outputFolders = useProcessingStore((s) => s.outputFolders);
  const startProcessing = useProcessingStore((s) => s.start);
  const setRunning = useProcessingStore((s) => s.setRunning);
  const appendLog = useProcessingStore((s) => s.appendLog);

  const [tiffList, setTiffList] = useState<TiffEntry[]>([]);
  const [models, setModels] = useState<YoloModel[]>([]);
  const [activeModelId, setActiveModelId] = useState<string>("");
  const [, setConfig] = useState<AppConfig>({});
  const [specs, setSpecs] = useState<SystemSpecs | null>(null);
  const [usage, setUsage] = useState<RealtimeUsage | null>(null);
  const [addGroupModal, setAddGroupModal] = useState<{
    name: string;
    tifPath: string;
    tfwPath: string;
  } | null>(null);
  const [addGroupName, setAddGroupName] = useState("");
  const [aiPackInstalled, setAiPackInstalled] = useState<boolean | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, c, m, tiffPaths] = await Promise.all([
        invoke<SystemSpecs>("get_specs"),
        invoke<AppConfig>("load_config_cmd").catch(() => ({})),
        invoke<YoloModel[]>("list_models_cmd").catch(() => []),
        invoke<string[]>("list_tiff_paths_cmd").catch(() => []),
      ]);
      setSpecs(s);
      setConfig(c);
      setModels(m);
      const active = m.find((x) => x.is_active);
      setActiveModelId(active ? String(active.id) : "");
      setTiffList(
        (tiffPaths as string[]).map((path) => ({ path, checked: false }))
      );
    } catch (e) {
      appendLog(`Error: ${e}`);
    }
  }, [appendLog]);

  useEffect(() => {
    load();
  }, [load]);

  // Cek AI pack terpasang + update saat download selesai.
  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const ok = await invoke<boolean>("check_ai_pack_installed");
        if (!cancelled) setAiPackInstalled(ok);
      } catch {
        if (!cancelled) setAiPackInstalled(false);
      }
    };

    void check();

    const unsubs: (() => void)[] = [];
    const setup = async () => {
      const u = await listen("ai-pack-done", () => {
        void check();
      });
      unsubs.push(u);
    };
    void setup();

    return () => {
      cancelled = true;
      unsubs.forEach((f) => f());
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const u = await invoke<RealtimeUsage>("get_realtime_usage_cmd");
        if (!cancelled) setUsage(u);
      } catch {
        /* ignore */
      }
    };
    void poll();
    const id = setInterval(poll, 1500);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const pickTiffTfw = async () => {
    const selected = await open({
      multiple: true,
      filters: [
        { name: "TIFF / TFW", extensions: ["tif", "tiff", "tfw"] },
      ],
    });
    if (!selected) return;
    const files = (Array.isArray(selected) ? selected : [selected]) as string[];
    const pairs = parseTiffTfwPairs(files);
    const existing = new Set(tiffList.map((t) => t.path));
    const toAdd = pairs.filter((p) => !existing.has(p.tifPath));
    if (toAdd.length === 0) {
      if (pairs.length === 0)
        appendLog(
          "Select matching .tif and .tfw pairs (same folder, same base name, e.g. UPE.tif + UPE.tfw)."
        );
      else appendLog("All selected groups are already in the list.");
      return;
    }
    if (toAdd.length === 1) {
      openAddGroupModal({
        name: toAdd[0].name,
        tifPath: toAdd[0].tifPath,
        tfwPath: toAdd[0].tfwPath,
      });
      return;
    }
    try {
      await invoke("add_tiff_paths_cmd", { paths: toAdd.map((p) => p.tifPath) });
      const added: TiffEntry[] = toAdd.map((p) => ({ path: p.tifPath, checked: false }));
      setTiffList((prev) => [...prev, ...added]);
      appendLog(`Added ${toAdd.length} groups: ${toAdd.map((p) => p.name).join(", ")}.`);
    } catch (e) {
      appendLog(`Error saving TIFF list: ${e}`);
    }
  };

  const confirmAddGroup = async () => {
    if (!addGroupModal) return;
    const name = addGroupName.trim() || addGroupModal.name;
    const { tifPath } = addGroupModal;
    try {
      await invoke("add_tiff_paths_cmd", { paths: [tifPath] });
      setTiffList((prev) => [...prev, { path: tifPath, checked: false }]);
      appendLog(`Added group "${name}" (${addGroupModal.name}.tif + ${addGroupModal.name}.tfw).`);
    } catch (e) {
      appendLog(`Error saving: ${e}`);
    }
    setAddGroupModal(null);
  };

  const openAddGroupModal = (m: { name: string; tifPath: string; tfwPath: string }) => {
    setAddGroupModal(m);
    setAddGroupName(m.name);
  };

  const removeTiff = async (path: string) => {
    if (running) return;
    try {
      await invoke("remove_tiff_path_cmd", { path });
      setTiffList((prev) => prev.filter((t) => t.path !== path));
    } catch (e) {
      appendLog(`Error removing: ${e}`);
    }
  };

  const setChecked = (path: string, checked: boolean) => {
    setTiffList((prev) =>
      prev.map((t) => (t.path === path ? { ...t, checked } : t))
    );
  };

  const selectAll = (checked: boolean) => {
    setTiffList((prev) => prev.map((t) => ({ ...t, checked })));
  };

  const checkedCount = tiffList.filter((t) => t.checked).length;
  const allChecked = tiffList.length > 0 && checkedCount === tiffList.length;
  const someChecked = checkedCount > 0;

  const run = async () => {
    const active = models.find((m) => String(m.id) === activeModelId);
    const modelName = active?.name ?? "";
    if (!modelName) {
      appendLog("Select an active YOLO model first.");
      return;
    }
    // Wajib AI pack terpasang (sidecar exe) sebelum mulai processing.
    try {
      const hasPack = await invoke<boolean>("check_ai_pack_installed");
      setAiPackInstalled(hasPack);
      if (!hasPack) {
        appendLog(
          "AI pack belum terpasang. Download AI pack terlebih dahulu dari banner di atas sebelum menjalankan processing."
        );
        return;
      }
    } catch {
      appendLog(
        "Tidak dapat mengecek status AI pack. Pastikan AI pack sudah terpasang sebelum menjalankan processing."
      );
      return;
    }

    const toProcess = tiffList.filter((t) => t.checked).map((t) => t.path);
    if (toProcess.length === 0) {
      appendLog("Select at least one TIFF (checkbox) to process.");
      return;
    }
    startProcessing();
    try {
      await invoke("run_processing_cmd", { files: toProcess, modelName });
    } catch (e) {
      appendLog(`Error: ${e}`);
      setRunning(false);
    }
  };

  const openResultFolder = async (path: string) => {
    const out = getOutputFolder(path, outputFolders);
    appendLog(`Open result folder: ${path.split(/[/\\]/).pop() ?? path}`);
    if (!out) {
      appendLog("No result folder for this file. Run processing first.");
      return;
    }
    try {
      await openPath(out);
    } catch (e1) {
      try {
        await revealItemInDir(out);
      } catch (e2) {
        appendLog(`Could not open folder: ${e1}`);
      }
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Status</CardTitle>
            <p className="text-xs text-muted-foreground">
              System specs and processing state
            </p>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {specs && (
              <dl className="grid gap-1.5">
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">OS</dt>
                  <dd className="font-medium">{specs.os}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">CPU</dt>
                  <dd className="font-medium">
                    {specs.cpu_cores}C / {specs.cpu_threads}T
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">RAM</dt>
                  <dd className="font-medium">{specs.total_ram_gb}</dd>
                </div>
                <div className="flex justify-between gap-2 items-center">
                  <dt className="text-muted-foreground">GPU</dt>
                  <dd>
                    <Badge
                      variant={
                        specs.gpu.includes("No") ? "destructive" : "default"
                      }
                      className="text-xs"
                    >
                      {specs.gpu} {specs.gpu_memory}
                    </Badge>
                  </dd>
                </div>
              </dl>
            )}
            {usage && (
              <div className="rounded-md border border-border/50 bg-muted/20 px-2.5 py-2 space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Live</p>
                <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
                  <span>
                    CPU{" "}
                    <span className="font-mono font-medium">
                      {usage.cpu_percent.toFixed(1)}%
                    </span>
                  </span>
                  {usage.gpu_percent != null && (
                    <span>
                      GPU{" "}
                      <span className="font-mono font-medium">
                        {usage.gpu_percent}%
                      </span>
                      {usage.gpu_memory_used_mb != null &&
                        usage.gpu_memory_total_mb != null && (
                          <span className="text-muted-foreground">
                            {" "}
                            ({(usage.gpu_memory_used_mb / 1024).toFixed(1)} /{" "}
                            {(usage.gpu_memory_total_mb / 1024).toFixed(1)} GB)
                          </span>
                        )}
                      {usage.gpu_temp_c != null && (
                        <span className="text-muted-foreground">
                          {" "}
                          {usage.gpu_temp_c}°C
                        </span>
                      )}
                    </span>
                  )}
                </div>
              </div>
            )}
            <div className="flex justify-between gap-2 pt-1 border-t border-border/50">
              <span className="text-muted-foreground">TIFF files</span>
              <span className="font-medium">{tiffList.length}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Process</span>
              <Badge variant={running ? "default" : "secondary"} className="text-xs">
                {running ? "Running" : "Idle"}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">File &amp; Model</CardTitle>
            <p className="text-xs text-muted-foreground">
              Select TIFFs, choose a model, then run
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">TIFF files</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={pickTiffTfw}
                    disabled={running}
                    className="gap-2"
                  >
                    <Plus className="h-4 w-4" />
                    Add TIFF + TFW
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  Select .tif and .tfw pairs (same folder, same base name, e.g. UPE.tif + UPE.tfw)
                </TooltipContent>
              </Tooltip>
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">YOLO Model</Label>
              <Select
                value={activeModelId}
                onValueChange={(v) => {
                  setActiveModelId(v);
                  invoke("set_active_model_cmd", { id: Number(v) });
                }}
                disabled={running}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  {models.map((m) => (
                    <SelectItem key={m.id} value={String(m.id)}>
                      {m.name} {m.is_active ? "(active)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {addGroupModal && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                <Card className="w-full max-w-sm border-border bg-card p-4 shadow-lg">
                  <p className="text-sm font-medium mb-2">Add group</p>
                  <p className="text-xs text-muted-foreground mb-2">
                    {addGroupModal.name}.tif + {addGroupModal.name}.tfw
                  </p>
                  <Label className="text-xs text-muted-foreground">Group name (e.g. UPE)</Label>
                  <Input
                    value={addGroupName}
                    onChange={(e) => setAddGroupName(e.target.value)}
                    placeholder={addGroupModal.name}
                    className="mt-1 mb-4"
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setAddGroupModal(null)}
                    >
                      Cancel
                    </Button>
                    <Button size="sm" onClick={confirmAddGroup}>
                      Add
                    </Button>
                  </div>
                </Card>
              </div>
            )}
            {tiffList.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="select-all"
                    checked={allChecked}
                    onCheckedChange={(c) => selectAll(!!c)}
                    disabled={running}
                  />
                  <Label
                    htmlFor="select-all"
                    className="text-sm font-normal cursor-pointer"
                  >
                    Select all ({checkedCount} selected)
                  </Label>
                </div>
                <ScrollArea className="h-36 rounded-lg border border-border/50 bg-muted/20 p-2">
                  <div className="space-y-1.5">
                    {tiffList.map((t) => (
                      <div
                        key={t.path}
                        className="flex items-center gap-2 text-sm rounded-md px-2 py-1.5 hover:bg-muted/50"
                      >
                        <Checkbox
                          checked={t.checked}
                          onCheckedChange={(c) => setChecked(t.path, !!c)}
                          disabled={running}
                        />
                        <span
                          className="flex-1 truncate font-mono text-xs"
                          title={t.path}
                        >
                          {(() => {
                            const base = t.path.split(/[/\\]/).pop() ?? t.path;
                            const s = stem(t.path);
                            return `${s} (${base} + ${s}.tfw)`;
                          })()}
                        </span>
                        {getOutputFolder(t.path, outputFolders) && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 shrink-0"
                            title="Open result folder"
                            onClick={() => openResultFolder(t.path)}
                          >
                            <FolderOpen className="h-4 w-4" />
                          </Button>
                        )}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                              onClick={() => removeTiff(t.path)}
                              disabled={running}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Remove from list</TooltipContent>
                        </Tooltip>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-block">
                  <Button
                    onClick={run}
                    disabled={
                      running ||
                      !activeModelId ||
                      !someChecked ||
                      aiPackInstalled === false
                    }
                    className="gap-2"
                  >
                    <Play className="h-4 w-4" />
                    Run processing
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {!activeModelId
                  ? "Select an active YOLO model first"
                  : !someChecked
                    ? "Select at least one TIFF to process"
                    : aiPackInstalled === false
                      ? "Install / download AI pack terlebih dahulu"
                      : "Process selected TIFFs with the active model"}
              </TooltipContent>
            </Tooltip>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
