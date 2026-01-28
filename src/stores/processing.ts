import { invoke } from "@tauri-apps/api/core";
import { create } from "zustand";

export interface ProcessingProgress {
  processed: number;
  total: number;
  current_file: string;
  status: string;
  abnormal_count: number;
  normal_count: number;
  output_folder?: string;
}

interface ProcessingState {
  running: boolean;
  progress: ProcessingProgress | null;
  log: string[];
  outputFolders: Record<string, string>;
  start: () => void;
  setRunning: (v: boolean) => void;
  appendLog: (line: string) => void;
  setProgress: (p: ProcessingProgress | null) => void;
  clearLog: () => void;
  cancel: () => void;
}

export const useProcessingStore = create<ProcessingState>((set) => ({
  running: false,
  progress: null,
  log: [],
  outputFolders: {},

  start: () =>
    set({
      running: true,
      progress: null,
      log: ["Starting processing..."],
      outputFolders: {},
    }),

  setRunning: (v) =>
    set((s) => ({
      running: v,
      progress: v ? s.progress : null,
    })),

  appendLog: (line) =>
    set((s) => ({ log: [...s.log, line] })),

  setProgress: (p) =>
    set((s) => {
      const next: Partial<ProcessingState> = { progress: p };
      if (p?.output_folder && p.current_file) {
        next.outputFolders = {
          ...s.outputFolders,
          [p.current_file]: p.output_folder,
        };
      }
      return next;
    }),

  clearLog: () => set({ log: [] }),

  cancel: () => {
    invoke("cancel_processing");
  },
}));
