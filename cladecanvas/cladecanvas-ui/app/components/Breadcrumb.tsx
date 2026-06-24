"use client";

import type { TreeNode } from "../lib/api";
import { isSynthetic } from "../lib/scoring";

type BreadcrumbEntry = {
  node: TreeNode;
  collapsedCount: number;
};

type Props = {
  lineage: TreeNode[];
  onSelect: (nodeId: string) => void;
};

function collapseSynthetic(lineage: TreeNode[]): BreadcrumbEntry[] {
  const entries: BreadcrumbEntry[] = [];
  let i = 0;
  while (i < lineage.length) {
    if (isSynthetic(lineage[i])) {
      const start = i;
      while (i < lineage.length && isSynthetic(lineage[i])) i++;
      entries.push({ node: lineage[start], collapsedCount: i - start });
    } else {
      entries.push({ node: lineage[i], collapsedCount: 1 });
      i++;
    }
  }
  return entries;
}

export default function Breadcrumb({ lineage, onSelect }: Props) {
  if (lineage.length <= 1) return null;

  const entries = collapseSynthetic(lineage);

  return (
    <nav
      className="text-sm py-2 flex items-center gap-0.5 overflow-x-auto whitespace-nowrap scrollbar-thin"
      style={{ color: "var(--color-ink-muted)" }}
    >
      {entries.map((entry, idx) => (
        <span key={entry.node.node_id} className="flex flex-none items-center gap-0.5">
          {idx > 0 && (
            <span className="mx-1 select-none" style={{ color: "var(--color-border)" }}>
              ›
            </span>
          )}
          <button
            onClick={() => onSelect(entry.node.node_id)}
            className="max-w-[12rem] truncate hover:underline transition-colors duration-150 sm:max-w-none"
            style={{
              fontFamily: entry.collapsedCount > 1 ? "var(--font-playfair), serif" : "inherit",
              fontStyle: entry.collapsedCount > 1 ? "italic" : "normal",
              color:
                idx === entries.length - 1
                  ? "var(--color-ink)"
                  : "var(--color-ink-muted)",
              fontWeight: idx === entries.length - 1 ? 600 : 400,
            }}
          >
            {entry.collapsedCount > 1
              ? "…"
              : entry.node.display_name || entry.node.name}
          </button>
        </span>
      ))}
    </nav>
  );
}
