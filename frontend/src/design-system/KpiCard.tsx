import React from "react";

interface KpiCardProps {
  label: string;
  value: string | number;
  delta?: {
    value: string | number;
    type: "positive" | "negative" | "neutral";
  };
  className?: string;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  delta,
  className = "",
}) => {
  return (
    <div className={`bg-deep border border-subtle rounded-[6px] p-[16px] flex flex-col justify-between hover:bg-card-hover/20 transition-all select-none ${className}`}>
      <span className="vdl-meta font-medium text-slate-500">
        {label}
      </span>
      <div className="flex items-baseline justify-between mt-2 gap-2">
        <span className="vdl-display leading-none">
          {value}
        </span>
        {delta && (
          <span
            className={`vdl-mono font-semibold px-1.5 py-0.5 rounded-[4px] border ${
              delta.type === "positive"
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/10"
                : delta.type === "negative"
                ? "bg-rose-500/10 text-rose-400 border-rose-500/10"
                : "bg-slate-500/10 text-slate-400 border-slate-500/10"
            }`}
          >
            {delta.type === "positive" ? "+" : ""}
            {delta.value}
          </span>
        )}
      </div>
    </div>
  );
};

export default KpiCard;
