"use client";

import React, { useEffect } from "react";
import Header from "@/components/shell/Header";
import EventBar from "@/components/shell/EventBar";
import CommandPalette from "@/components/shell/CommandPalette";
import WorkspaceHost from "@/components/workspace/WorkspaceHost";
import { useEventStore } from "@/store/useEventStore";
import { useThemeStore } from "@/store/useThemeStore";

export default function ValkyrieCommandRoom() {
  const addEvent = useEventStore((state) => state.addEvent);
  const theme = useThemeStore((state) => state.theme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Dispatch an initialization event on load
  useEffect(() => {
    addEvent({
      type: "success",
      message: "Valkyrie Modern Terminal Shell framework initialized successfully",
      workspace: "System",
    });
  }, []);

  return (
    <div className="flex flex-row min-h-screen w-full bg-bg-deep text-text-main font-sans overflow-hidden">
      {/* Main Right Side Content Container */}
      <div className="flex-1 flex flex-col min-w-0 h-screen relative">
        {/* Top Fixed Header inside Right Content Area */}
        <Header />

        {/* Dynamic Workspace Container */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden p-0">
          <WorkspaceHost />
        </main>

        {/* Bottom Fixed Event Bar inside Right Content Area */}
        <EventBar />
      </div>

      {/* Global Command Palette Overlay (Ctrl + K) */}
      <CommandPalette />
    </div>
  );
}
