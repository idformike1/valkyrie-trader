import React from "react";
import { HelpCircle } from "lucide-react";

interface EmptyStateProps {
  icon?: React.ComponentType<any>;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = HelpCircle,
  title,
  description,
  action,
  className = "",
}) => {
  return (
    <div className={`flex flex-col items-center justify-center p-[24px] text-center border border-dashed border-subtle/50 rounded-[8px] bg-deep/20 select-none ${className}`}>
      <div className="w-[36px] h-[36px] rounded-full bg-slate-900 border border-subtle flex items-center justify-center text-slate-500 mb-3">
        <Icon className="w-5 h-5" />
      </div>
      <h4 className="vdl-section text-slate-300">
        {title}
      </h4>
      <p className="vdl-meta text-slate-500 max-w-[280px] mt-1">
        {description}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
};

export default EmptyState;
