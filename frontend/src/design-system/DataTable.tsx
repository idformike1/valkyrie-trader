import React from "react";

export interface ColumnDef<T> {
  header: string;
  accessorKey: keyof T | ((row: T, index: number) => React.ReactNode);
  className?: string;
  isNumeric?: boolean;
  isMono?: boolean;
}

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T) => string;
  emptyState?: React.ReactNode;
  className?: string;
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  rowClassName,
  emptyState,
  className = "",
}: DataTableProps<T>) {
  return (
    <div className={`w-full overflow-x-auto ${className}`}>
      <table className="w-full text-left border-collapse select-none">
        <thead>
          <tr className="border-b border-subtle bg-bg-deep h-[36px]">
            {columns.map((col, idx) => (
              <th
                key={idx}
                className={`px-[12px] vdl-meta font-bold text-slate-200 normal-case tracking-normal ${
                  col.isNumeric ? "text-right" : "text-left"
                } ${col.className || ""}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-subtle/40">
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center">
                {emptyState || (
                  <span className="vdl-meta text-slate-500">
                    No data available
                  </span>
                )}
              </td>
            </tr>
          ) : (
            data.map((row, rowIdx) => {
              const customClasses = rowClassName ? rowClassName(row) : "";
              return (
                <tr
                  key={rowIdx}
                  onClick={() => onRowClick && onRowClick(row)}
                  className={`h-[38px] transition-colors border-b border-subtle/20 ${
                    onRowClick ? "cursor-pointer hover:bg-card-hover" : "hover:bg-card-hover/40"
                  } ${customClasses}`}
                >
                {columns.map((col, colIdx) => {
                  let content: React.ReactNode;
                  if (typeof col.accessorKey === "function") {
                    content = col.accessorKey(row, rowIdx);
                  } else {
                    const val = row[col.accessorKey];
                    content = val !== undefined && val !== null ? String(val) : "";
                  }

                  return (
                    <td
                       key={colIdx}
                       className={`px-[12px] ${
                         col.isMono ? "vdl-mono" : "vdl-body"
                       } ${col.isNumeric ? "text-right" : "text-left"} ${
                         col.className || ""
                       }`}
                    >
                      {content}
                    </td>
                  );
                })}
              </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;
