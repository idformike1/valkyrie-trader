import { create } from "zustand";

interface ThemeState {
  theme: "dark";
}

export const useThemeStore = create<ThemeState>(() => ({
  theme: "dark",
}));
