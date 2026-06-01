import { create } from "zustand";

interface ThemeState {
  theme: "navy" | "light";
  setTheme: (theme: "navy" | "light") => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: "navy",
  setTheme: (theme) => set({ theme }),
}));
