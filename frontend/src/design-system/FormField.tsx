import React from "react";

interface FormFieldProps {
  label: string;
  children: React.ReactNode;
  error?: string;
  helpText?: string;
  className?: string;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  children,
  error,
  helpText,
  className = "",
}) => {
  return (
    <div className={`flex flex-col gap-[4px] w-full font-sans ${className}`}>
      <label className="vdl-meta font-semibold text-slate-400 select-none">
        {label}
      </label>
      <div className="relative flex flex-col">
        {children}
      </div>
      {error ? (
        <span className="text-[10px] text-rose-400 font-medium">{error}</span>
      ) : helpText ? (
        <span className="text-[10px] text-slate-500">{helpText}</span>
      ) : null}
    </div>
  );
};

interface FormSectionProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export const FormSection: React.FC<FormSectionProps> = ({
  title,
  children,
  className = "",
}) => {
  return (
    <div className={`flex flex-col gap-[12px] border-b border-subtle/30 pb-4 last:border-b-0 last:pb-0 ${className}`}>
      {title && (
        <h4 className="vdl-meta font-bold text-slate-500 uppercase tracking-widest border-l-2 border-cyan-neon pl-2 select-none">
          {title}
        </h4>
      )}
      <div className="flex flex-col gap-[8px]">
        {children}
      </div>
    </div>
  );
};
