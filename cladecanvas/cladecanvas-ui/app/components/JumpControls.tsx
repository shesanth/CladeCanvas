"use client";

import type { NavigationMode, TreeNode } from "../lib/api";

type Props = {
  mode: NavigationMode;
  parent: TreeNode | null;
  childNodes: TreeNode[];
  siblings: TreeNode[];
  onSelect: (nodeId: string) => void;
  onModeChange: (mode: NavigationMode) => void;
};

export default function JumpControls({
  mode,
  parent,
  childNodes,
  siblings,
  onSelect,
  onModeChange,
}: Props) {
  const firstChild = childNodes[0] ?? null;
  const firstSibling = siblings[0] ?? null;

  return (
    <div
      className="flex flex-wrap items-center gap-2 py-2.5 sm:py-3"
      aria-label="Navigation controls"
    >
      <button
        type="button"
        onClick={() => parent && onSelect(parent.node_id)}
        disabled={!parent}
        title="Jump to parent"
        aria-label="Jump to parent"
        className="nav-control"
      >
        ↑
      </button>
      <button
        type="button"
        onClick={() => firstSibling && onSelect(firstSibling.node_id)}
        disabled={!firstSibling}
        title="Jump to next sibling"
        aria-label="Jump to next sibling"
        className="nav-control"
      >
        ↔
      </button>
      <button
        type="button"
        onClick={() => firstChild && onSelect(firstChild.node_id)}
        disabled={!firstChild}
        title="Jump to first child"
        aria-label="Jump to first child"
        className="nav-control"
      >
        ↓
      </button>

      <div
        className="mt-1 inline-flex w-full overflow-hidden rounded-md sm:mt-0 sm:ml-auto sm:w-auto"
        style={{ border: "1px solid var(--color-border)" }}
      >
        {(["local", "overview"] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onModeChange(option)}
            className="min-h-10 flex-1 px-3 py-2 text-xs font-medium capitalize transition-colors sm:min-h-0 sm:flex-none sm:py-1.5"
            aria-pressed={mode === option}
            style={{
              background:
                mode === option ? "var(--color-accent)" : "var(--color-paper-light)",
              color: mode === option ? "white" : "var(--color-ink-muted)",
              borderRight:
                option === "local" ? "1px solid var(--color-border)" : "none",
            }}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}
