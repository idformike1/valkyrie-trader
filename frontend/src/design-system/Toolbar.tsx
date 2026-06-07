import React from "react";

interface ToolbarProps {
  title?: string;
  leftControls?: React.ReactNode;
  rightControls?: React.ReactNode;
  className?: string;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  title,
  leftControls,
  rightControls,
  className = "",
}) => {
  return (
    <div
      className={`h-[40px] px-4 border-b border-subtle bg-deep flex items-center justify-between shrink-0 select-none ${className}`}
    >
      <div className="flex items-center gap-[12px]">
        {title && (
          <h2 className="vdl-section font-bold text-main border-r border-subtle pr-3 mr-1">
            {title}
          </h2>
        )}
        <div className="flex items-center gap-[8px]">
          {leftControls}
        </div>
      </div>
      <div className="flex items-center gap-[12px]">
        {rightControls}
      </div>
    </div>
  );
};

export default Toolbar;
