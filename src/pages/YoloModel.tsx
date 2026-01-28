import { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Loader2, Plus } from "lucide-react";
import { useConversionStore } from "@/stores/conversion";

interface YoloModel {
  id: number;
  name: string;
  path: string;
  is_active: boolean;
}

export function YoloModelPage() {
  const [models, setModels] = useState<YoloModel[]>([]);
  const status = useConversionStore((s) => s.status);
  const isAdding = useConversionStore((s) => s.isAdding);
  const setStatus = useConversionStore((s) => s.setStatus);

  const load = useCallback(async () => {
    try {
      const m = await invoke<YoloModel[]>("list_models_cmd");
      setModels(m);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addModel = async () => {
    const selected = await open({
      multiple: true,  // Enable multiple file selection
      filters: [{ name: "YOLO model", extensions: ["pt", "onnx"] }],
    });
    if (!selected) return;
    
    // Handle both single and multiple selection
    const files = Array.isArray(selected) ? selected : [selected];
    if (files.length === 0) return;
    
    setStatus(null, true);

    try {
      if (files.length === 1) {
        await invoke("add_model_cmd", { sourcePath: files[0], name: undefined });
      } else {
        await invoke("add_models_cmd", { sourcePaths: files });
      }
      await load();
    } catch (e) {
      console.error(e);
      setStatus(`Error: ${e}`, false);
      setTimeout(() => setStatus(null, false), 5000);
    } finally {
      if (files.length === 1) {
        setStatus(null, false);
      } else {
        setTimeout(() => setStatus(null, false), 3000);
      }
    }
  };

  const remove = async (id: number) => {
    try {
      await invoke("remove_model_cmd", { id });
      await load();
    } catch (e) {
      console.error(e);
    }
  };

  const setActive = async (id: number) => {
    try {
      await invoke("set_active_model_cmd", { id });
      await load();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <Card className="border-border/50">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base">YOLO Model Library</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">
              Add .pt or .onnx models and set one as default for inference
            </p>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button onClick={addModel} disabled={isAdding} className="gap-2">
                {isAdding ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Adding…
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4" />
                    Add model
                  </>
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Add .pt or .onnx YOLO models</TooltipContent>
          </Tooltip>
        </CardHeader>
        <CardContent className="space-y-4">
          {status && (
            <div
              className={
                status.startsWith("Error")
                  ? "rounded-lg border border-destructive/30 bg-destructive/10 p-3"
                  : status.includes("Successfully")
                    ? "rounded-lg border border-green-500/30 bg-green-500/10 dark:bg-green-500/5 dark:border-green-500/20 p-3"
                    : "rounded-lg border border-border bg-muted/50 p-3"
              }
            >
              <div className="flex items-center gap-2">
                {isAdding && <Loader2 className="h-4 w-4 animate-spin shrink-0" />}
                <p
                  className={
                    status.startsWith("Error")
                      ? "text-sm text-destructive"
                      : status.includes("Successfully")
                        ? "text-sm text-green-600 dark:text-green-400"
                        : "text-sm"
                  }
                >
                  {status}
                </p>
              </div>
              {isAdding && <Progress value={undefined} className="mt-2" />}
            </div>
          )}
          {models.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/60 bg-muted/20 py-12 text-center">
              <p className="text-sm text-muted-foreground">
                No models yet. Add a .pt or .onnx file to get started.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Path</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead className="w-[200px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {models.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium">{m.name}</TableCell>
                    <TableCell
                      className="max-w-[280px] truncate font-mono text-xs text-muted-foreground"
                      title={m.path}
                    >
                      {m.path}
                    </TableCell>
                    <TableCell>
                      {m.is_active ? (
                        <Badge variant="default" className="text-xs">
                          Active
                        </Badge>
                      ) : (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setActive(m.id)}
                            >
                              Set default
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Use this model for processing</TooltipContent>
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => remove(m.id)}
                          >
                            Remove
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Remove from library</TooltipContent>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
