import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface AppConfig {
  imgsz?: string;
  iou?: string;
  conf?: string;
  device?: string;
  max_det?: string;
  line_width?: string;
  convert_kml?: string;
  convert_shp?: string;
  save_annotated?: string;
  show_labels?: string;
  show_conf?: string;
}

export function SettingsPage() {
  const [config, setConfig] = useState<AppConfig>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    invoke<AppConfig>("load_config_cmd")
      .then(setConfig)
      .catch(() => {});
  }, []);

  const update = (k: keyof AppConfig, v: string | undefined) =>
    setConfig((c) => ({ ...c, [k]: v }));

  const save = async () => {
    try {
      await invoke("save_config_cmd", { c: config });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 p-6">
      <Card className="border-border/50">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base">Processing settings</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">
              Inference parameters and output options
            </p>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button onClick={save} variant={saved ? "secondary" : "default"}>
                {saved ? "Saved" : "Save"}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Persist settings to disk</TooltipContent>
          </Tooltip>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <p className="text-sm font-medium mb-3">Parameters</p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-xs">Image size (imgsz)</Label>
                <Input
                  value={config.imgsz ?? "12800"}
                  onChange={(e) => update("imgsz", e.target.value)}
                  className="h-9"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Confidence</Label>
                <Input
                  value={config.conf ?? "0.2"}
                  onChange={(e) => update("conf", e.target.value)}
                  className="h-9"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">IOU</Label>
                <Input
                  value={config.iou ?? "0.2"}
                  onChange={(e) => update("iou", e.target.value)}
                  className="h-9"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Max detections</Label>
                <Input
                  value={config.max_det ?? "10000"}
                  onChange={(e) => update("max_det", e.target.value)}
                  className="h-9"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Line width</Label>
                <Input
                  value={config.line_width ?? "3"}
                  onChange={(e) => update("line_width", e.target.value)}
                  className="h-9"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Device</Label>
                <Input
                  value={config.device ?? "auto"}
                  onChange={(e) => update("device", e.target.value)}
                  placeholder="auto | cpu | cuda"
                  className="h-9"
                />
              </div>
            </div>
          </div>
          <Separator />
          <div>
            <p className="text-sm font-medium mb-3">Output options</p>
            <div className="flex flex-wrap gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={config.convert_kml === "true"}
                  onCheckedChange={(c) =>
                    update("convert_kml", c ? "true" : "false")
                  }
                />
                <span className="text-sm">Convert KML</span>
              </label>
              <div className="space-y-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={config.convert_shp !== "false"}
                    onCheckedChange={(c) =>
                      update("convert_shp", c ? "true" : "false")
                    }
                  />
                  <span className="text-sm">Convert Shapefile</span>
                </label>
                <p className="text-xs text-muted-foreground pl-6">
                  Shapefile and KML require a .tfw next to each TIFF (same base name, e.g. UPE.tfw for UPE.tif). Add pairs via &quot;Add TIFF + TFW&quot; on Dashboard.
                </p>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={config.save_annotated !== "false"}
                  onCheckedChange={(c) =>
                    update("save_annotated", c ? "true" : "false")
                  }
                />
                <span className="text-sm">Save annotated images</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={config.show_labels !== "false"}
                  onCheckedChange={(c) =>
                    update("show_labels", c ? "true" : "false")
                  }
                />
                <span className="text-sm">Show labels</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={config.show_conf === "true"}
                  onCheckedChange={(c) =>
                    update("show_conf", c ? "true" : "false")
                  }
                />
                <span className="text-sm">Show confidence</span>
              </label>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
