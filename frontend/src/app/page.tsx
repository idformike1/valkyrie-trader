"use client";

import React, { useEffect } from "react";
import Header from "@/components/shell/Header";
import Sidebar from "@/components/shell/Sidebar";
import EventBar from "@/components/shell/EventBar";
import CommandPalette from "@/components/shell/CommandPalette";
import WorkspaceHost from "@/components/workspace/WorkspaceHost";
import { useSidebarStore } from "@/store/useSidebarStore";
import { useEventStore } from "@/store/useEventStore";

export default function ValkyrieCommandRoom() {
  const isCollapsed = useSidebarStore((state) => state.isCollapsed);
  const addEvent = useEventStore((state) => state.addEvent);

  // Dispatch an initialization event on load
  useEffect(() => {
    addEvent({
      type: "success",
      message: "Valkyrie Modern Terminal Shell framework initialized successfully",
      workspace: "System",
    });
  }, []);

  return (
    <div className="flex flex-col min-h-screen w-full bg-bg-deep text-text-main font-sans overflow-hidden">
      {/* Top Fixed Header */}
      <Header />

      {/* Main Layout Area */}
      <div className="flex-1 flex flex-row w-full pt-11 pb-6 min-h-0 relative">
        {/* Collapsible Left Sidebar */}
        <Sidebar />

        {/* Dynamic Workspace Container */}
        <main
          style={{
            paddingLeft: isCollapsed ? "56px" : "220px",
            transition: "padding-left 0.2s ease-in-out",
          }}
          className="flex-1 flex flex-col min-w-0 h-full overflow-hidden"
        >
          <WorkspaceHost />
        </main>
      </div>

      {/* Bottom Fixed Event Bar */}
      <EventBar />

      {/* Global Command Palette Overlay (Ctrl + K) */}
      <CommandPalette />
    </div>
  );
}
