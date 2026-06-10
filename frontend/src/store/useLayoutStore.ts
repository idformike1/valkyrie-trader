import { create } from "zustand";
import { persist } from "zustand/middleware";

interface WorkspaceLayout {
  leftWidth?: number;
  rightWidth?: number;
  bottomHeight?: number;
  leftCollapsed?: boolean;
  rightCollapsed?: boolean;
  bottomCollapsed?: boolean;
}

interface LayoutState {
  layouts: Record<string, WorkspaceLayout>;
  updateSize: (workspaceId: string, panel: "left" | "right" | "bottom", size: number) => void;
  toggleCollapse: (workspaceId: string, panel: "left" | "right" | "bottom") => void;
  setCollapsed: (workspaceId: string, panel: "left" | "right" | "bottom", collapsed: boolean) => void;
  resetLayout: (workspaceId: string) => void;
}

const DEFAULT_LAYOUTS: Record<string, WorkspaceLayout> = {
  trading: { leftWidth: 280, rightWidth: 320, bottomHeight: 220, leftCollapsed: false, rightCollapsed: false, bottomCollapsed: false },
  scalper: { leftWidth: 0, rightWidth: 340, bottomHeight: 200, leftCollapsed: true, rightCollapsed: false, bottomCollapsed: false }, // Scalper might not need a left panel
  backtest: { leftWidth: 260, rightWidth: 320, bottomHeight: 220, leftCollapsed: false, rightCollapsed: false, bottomCollapsed: false },
  paper: { leftWidth: 220, rightWidth: 240, bottomHeight: 320, leftCollapsed: false, rightCollapsed: false, bottomCollapsed: false },
  deployments: { leftWidth: 240, rightWidth: 0, bottomHeight: 200, leftCollapsed: false, rightCollapsed: true, bottomCollapsed: false },
  operations: { leftWidth: 250, rightWidth: 250, bottomHeight: 250, leftCollapsed: false, rightCollapsed: false, bottomCollapsed: false },
};

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      layouts: DEFAULT_LAYOUTS,
      updateSize: (workspaceId, panel, size) =>
        set((state) => {
          const workspaceLayout = state.layouts[workspaceId] || {};
          const updated: WorkspaceLayout = { ...workspaceLayout };
          if (panel === "left") updated.leftWidth = size;
          if (panel === "right") updated.rightWidth = size;
          if (panel === "bottom") updated.bottomHeight = size;

          return {
            layouts: {
              ...state.layouts,
              [workspaceId]: updated,
            },
          };
        }),
      toggleCollapse: (workspaceId, panel) =>
        set((state) => {
          const workspaceLayout = state.layouts[workspaceId] || {};
          const updated: WorkspaceLayout = { ...workspaceLayout };
          if (panel === "left") updated.leftCollapsed = !workspaceLayout.leftCollapsed;
          if (panel === "right") updated.rightCollapsed = !workspaceLayout.rightCollapsed;
          if (panel === "bottom") updated.bottomCollapsed = !workspaceLayout.bottomCollapsed;

          return {
            layouts: {
              ...state.layouts,
              [workspaceId]: updated,
            },
          };
        }),
      setCollapsed: (workspaceId, panel, collapsed) =>
        set((state) => {
          const workspaceLayout = state.layouts[workspaceId] || {};
          const updated: WorkspaceLayout = { ...workspaceLayout };
          if (panel === "left") updated.leftCollapsed = collapsed;
          if (panel === "right") updated.rightCollapsed = collapsed;
          if (panel === "bottom") updated.bottomCollapsed = collapsed;

          return {
            layouts: {
              ...state.layouts,
              [workspaceId]: updated,
            },
          };
        }),
      resetLayout: (workspaceId) =>
        set((state) => ({
          layouts: {
            ...state.layouts,
            [workspaceId]: DEFAULT_LAYOUTS[workspaceId] || {},
          },
        })),
    }),
    {
      name: "valkyrie-layout-storage",
    }
  )
);
