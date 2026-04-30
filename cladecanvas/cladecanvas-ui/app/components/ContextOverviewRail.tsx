"use client";

import type { ContextGraph, ContextGraphNode } from "../lib/api";

type Props = {
  graph: ContextGraph | null;
  selectedNodeId: string;
  onSelect: (nodeId: string) => void;
};

function labelFor(node: ContextGraphNode): string {
  return node.display_name || node.name;
}

export default function ContextOverviewRail({
  graph,
  selectedNodeId,
  onSelect,
}: Props) {
  if (!graph) return null;

  const lineage = graph.nodes.filter((node) => node.kind === "lineage");
  const sideNodes = graph.nodes.filter((node) => node.kind !== "lineage");
  const maxDepth = Math.max(...graph.nodes.map((node) => node.depth), 1);

  return (
    <aside
      className="overview-rail"
      aria-label="Context overview"
      style={{
        background: "var(--color-paper-light)",
        border: "1px solid var(--color-border)",
      }}
    >
      <div className="overview-rail__spine" aria-hidden="true" />
      {lineage.map((node, index) => {
        const top = 8 + (node.depth / maxDepth) * 78;
        const isSelected = node.node_id === selectedNodeId;
        return (
          <button
            key={node.node_id}
            type="button"
            className="overview-rail__node"
            onClick={() => onSelect(node.node_id)}
            title={labelFor(node)}
            aria-label={`Jump to ${labelFor(node)}`}
            style={{
              top: `${top}%`,
              left: "40%",
              width: isSelected ? 16 : 11,
              height: isSelected ? 16 : 11,
              background: isSelected
                ? "var(--clade-node-ring)"
                : "var(--clade-node-dot)",
              opacity: 1 - Math.min(index, 6) * 0.04,
            }}
          />
        );
      })}
      {sideNodes.map((node, index) => {
        const top = 8 + (node.depth / maxDepth) * 78;
        const isChild = node.kind === "child";
        return (
          <button
            key={`${node.kind}-${node.node_id}`}
            type="button"
            className="overview-rail__node overview-rail__node--side"
            onClick={() => onSelect(node.node_id)}
            title={labelFor(node)}
            aria-label={`Jump to ${labelFor(node)}`}
            style={{
              top: `${top}%`,
              left: isChild ? `${58 + (index % 3) * 9}%` : `${18 - (index % 2) * 8}%`,
              width: isChild ? 8 : 7,
              height: isChild ? 8 : 7,
              background: isChild ? "var(--color-accent)" : "var(--color-ink-muted)",
            }}
          />
        );
      })}
      <div className="overview-rail__label">
        {lineage.length} levels
      </div>
    </aside>
  );
}
