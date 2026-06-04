import { create } from "zustand";

interface ThemeState {
  theme: "navy" | "light" | "blackstone";
  setTheme: (theme: "navy" | "light" | "blackstone") => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: "navy",
  setTheme: (theme) => set({ theme }),
}));
