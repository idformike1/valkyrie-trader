import React from "react";

export type PanelType = "left" | "main" | "right" | "bottom";

export interface WorkspacePanelProps {
  workspaceId: string;
}

export interface WorkspaceConfig {
  id: string;
  name: string;
  description: string;
  icon: string; // Name of the lucide icon
  panels: {
    left?: React.ComponentType<WorkspacePanelProps>;
    main: React.ComponentType<WorkspacePanelProps>;
    right?: React.ComponentType<WorkspacePanelProps>;
    bottom?: React.ComponentType<WorkspacePanelProps>;
  };
}
