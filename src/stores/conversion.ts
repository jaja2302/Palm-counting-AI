import { create } from "zustand";

interface ConversionState {
  status: string | null;
  isAdding: boolean;
  setStatus: (status: string | null, isAdding: boolean) => void;
}

export const useConversionStore = create<ConversionState>((set) => ({
  status: null,
  isAdding: false,
  setStatus: (status, isAdding) => set({ status, isAdding }),
}));
