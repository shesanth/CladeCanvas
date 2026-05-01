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

function shortLabel(value: string): string {
  return value.length > 22 ? `${value.slice(0, 21)}...` : value;
}

function tipsLabel(value?: number | null): string | null {
  if (!value) return null;
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M spp.`;
  if (value >= 1000) return `${Math.round(value / 1000)}k spp.`;
  return `${value.toLocaleString()} spp.`;
}

export default function ContextOverviewRail({
  graph,
  selectedNodeId,
  onSelect,
}: Props) {
  if (!graph) return null;

  const lineage = graph.nodes.filter((node) => node.kind === "lineage");
  const selected = lineage.find((node) => node.node_id === selectedNodeId);
  const visibleLineage =
    lineage.length > 7
      ? [lineage[0], ...lineage.slice(-6)]
      : lineage;
  const hiddenLineageCount = Math.max(0, lineage.length - visibleLineage.length);
  const siblings = graph.nodes.filter((node) => node.kind === "sibling").slice(-4);
  const children = graph.nodes.filter((node) => node.kind === "child").slice(0, 5);

  return (
    <aside
      className="overview-rail"
      aria-label="Context overview"
      style={{
        background: "var(--color-paper-light)",
        border: "1px solid var(--color-border)",
      }}
    >
      <div className="overview-rail__summary">
        <span>{lineage.length} levels</span>
        {selected?.rank && <span className="capitalize">{selected.rank}</span>}
      </div>

      <div className="overview-rail__path" aria-label="Current lineage">
        {visibleLineage.map((node, index) => {
          const isSelected = node.node_id === selectedNodeId;
          const isRoot = index === 0 && hiddenLineageCount > 0;
          const showGap = index === 1 && hiddenLineageCount > 0;
          const tips = tipsLabel(node.num_tips);
          return (
            <div key={node.node_id} className="overview-rail__path-row">
              {showGap && (
                <div className="overview-rail__gap">
                  {hiddenLineageCount} intermediate levels
                </div>
              )}
              <button
                type="button"
                className={`overview-rail__path-button${
                  isSelected ? " overview-rail__path-button--active" : ""
                }${isRoot ? " overview-rail__path-button--root" : ""}`}
                onClick={() => onSelect(node.node_id)}
                title={labelFor(node)}
                aria-current={isSelected ? "true" : undefined}
              >
                <span className="overview-rail__dot" aria-hidden="true" />
                <span className="overview-rail__path-copy">
                  <span>{shortLabel(labelFor(node))}</span>
                  {tips && <small>{tips}</small>}
                </span>
              </button>
            </div>
          );
        })}
      </div>

      {(siblings.length > 0 || children.length > 0) && (
        <div className="overview-rail__branches">
          {siblings.length > 0 && (
            <section>
              <h3>Nearby</h3>
              {siblings.map((node) => (
                <button
                  key={`sibling-${node.node_id}`}
                  type="button"
                  onClick={() => onSelect(node.node_id)}
                  title={labelFor(node)}
                >
                  {shortLabel(labelFor(node))}
                </button>
              ))}
            </section>
          )}

          {children.length > 0 && (
            <section>
              <h3>Children</h3>
              {children.map((node) => (
                <button
                  key={`child-${node.node_id}`}
                  type="button"
                  onClick={() => onSelect(node.node_id)}
                  title={labelFor(node)}
                >
                  {shortLabel(labelFor(node))}
                </button>
              ))}
            </section>
          )}
        </div>
      )}
    </aside>
  );
}
