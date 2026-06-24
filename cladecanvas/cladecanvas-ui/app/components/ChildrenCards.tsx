"use client";

import { useEffect, useState } from "react";
import type { TreeNode } from "../lib/api";
import { score } from "../lib/scoring";

type Props = {
  nodes: TreeNode[];
  onSelect: (nodeId: string) => void;
};

const MAX_CARDS = 12;

export default function ChildrenCards({ nodes, onSelect }: Props) {
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    setShowAll(false);
  }, [nodes]);

  if (nodes.length === 0) return null;

  const sorted = [...nodes].sort((a, b) => score(b) - score(a));
  const visible = showAll ? sorted : sorted.slice(0, MAX_CARDS);
  const overflow = Math.max(0, sorted.length - MAX_CARDS);

  return (
    <div>
      <h3
        className="text-xs uppercase tracking-wider mb-3 font-semibold"
        style={{ color: "var(--color-ink-muted)" }}
      >
        Notable children
      </h3>
      <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2 scrollbar-thin snap-x snap-mandatory sm:mx-0 sm:px-0">
        {visible.map((node) => (
          <button
            key={node.node_id}
            onClick={() => onSelect(node.node_id)}
            className="flex-shrink-0 snap-start rounded-lg p-3 text-left transition-all duration-200 hover:-translate-y-0.5 w-40 sm:w-36"
            style={{
              background: "var(--color-paper)",
              border: "1px solid var(--color-border)",
              boxShadow: "0 1px 3px rgba(44, 36, 22, 0.06)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow =
                "0 4px 12px rgba(44, 36, 22, 0.12)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow =
                "0 1px 3px rgba(44, 36, 22, 0.06)";
            }}
          >
            <p
              className="text-sm font-medium leading-tight truncate"
              style={{
                fontFamily: "var(--font-playfair), serif",
                color: "var(--color-ink)",
              }}
            >
              {node.display_name || node.name}
            </p>
            {node.rank && (
              <span
                className="text-[10px] mt-1 inline-block px-1.5 py-0.5 rounded-full capitalize"
                style={{
                  background: "var(--color-border)",
                  color: "var(--color-ink-muted)",
                }}
              >
                {node.rank}
              </span>
            )}
            {node.num_tips != null && (
              <p
                className="text-xs mt-1"
                style={{ color: "var(--color-ink-muted)" }}
              >
                {node.num_tips.toLocaleString()} spp.
              </p>
            )}
          </button>
        ))}

        {overflow > 0 && !showAll && (
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="flex-shrink-0 snap-start rounded-lg p-3 flex items-center justify-center w-24 transition-all duration-200 hover:-translate-y-0.5"
            style={{
              background: "var(--color-paper)",
              border: "1px dashed var(--color-border)",
              color: "var(--color-ink-muted)",
            }}
            aria-label={`Show ${overflow} more children`}
          >
            <span className="text-sm font-medium">+{overflow} more</span>
          </button>
        )}
      </div>
    </div>
  );
}

