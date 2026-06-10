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
    <div className={`flex flex-col items-center justify-center p-[32px] text-center border border-dashed border-subtle/60 rounded-[8px] bg-deep/40 select-none ${className}`}>
      <div className="w-[40px] h-[40px] rounded-full bg-slate-900/80 border border-subtle flex items-center justify-center text-slate-400 mb-4">
        <Icon className="w-5 h-5" />
      </div>
      <h4 className="vdl-section text-slate-200">
        {title}
      </h4>
      <p className="vdl-meta text-slate-400 max-w-[320px] mt-1.5 leading-relaxed">
        {description}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
};

export default EmptyState;
