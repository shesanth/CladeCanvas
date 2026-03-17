"use client";

import { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { TreeNode } from "../lib/api";
import { computeLayout, type BranchPath } from "../lib/tree-layout";
import CladogramNode from "./CladogramNode";

type Props = {
  parent: TreeNode | null;
  siblings: TreeNode[];
  selected: TreeNode;
  childNodes: TreeNode[];
  onSelect: (nodeId: string) => void;
};

export default function LocalCladogram({
  parent,
  siblings,
  selected,
  childNodes,
  onSelect,
}: Props) {
  const [ripple, setRipple] = useState<{ x: number; y: number; key: number } | null>(
    null
  );
  const rippleCounter = useRef(0);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const layout = computeLayout(parent, siblings, selected, childNodes);
  const { nodes, paths, width, height, overflowSiblings, overflowChildren } = layout;

  const handleNodeClick = useCallback(
    (nodeId: string, x: number, y: number) => {
      if (nodeId === selected.node_id || isTransitioning) return;

      rippleCounter.current += 1;
      setRipple({ x, y, key: rippleCounter.current });
      setIsTransitioning(true);

      setTimeout(() => {
        onSelect(nodeId);
        setIsTransitioning(false);
      }, 150);
    },
    [selected.node_id, onSelect, isTransitioning]
  );

  const svgHeight = Math.max(height, 200);

  return (
    <div
      className="w-full max-w-4xl mx-auto overflow-x-auto my-4 rounded-xl"
      style={{ background: "var(--color-paper-light)" }}
    >
      <svg
        width="100%"
        height={svgHeight}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Key the ENTIRE content on selected node so we get a clean swap */}
        <AnimatePresence>
          <motion.g
            key={selected.node_id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {/* Branch paths */}
            {paths.map((path, idx) => (
              <BranchPathElement
                key={`${path.fromId}-${path.toId}`}
                path={path}
                delay={0.05 * idx}
              />
            ))}

            {/* Nodes */}
            {nodes.map((layoutNode, idx) => (
              <CladogramNode
                key={`${layoutNode.column}-${layoutNode.node.node_id}`}
                node={layoutNode.node}
                x={layoutNode.x}
                y={layoutNode.y}
                isSelected={layoutNode.isSelected}
                column={layoutNode.column}
                onClick={() =>
                  handleNodeClick(
                    layoutNode.node.node_id,
                    layoutNode.x,
                    layoutNode.y
                  )
                }
                animationDelay={
                  layoutNode.column === "parent"
                    ? 0.05
                    : layoutNode.column === "sibling"
                    ? 0.1 + idx * 0.03
                    : layoutNode.column === "selected"
                    ? 0.05
                    : 0.15 + idx * 0.03
                }
              />
            ))}

            {/* Overflow indicators */}
            {overflowSiblings > 0 && (() => {
              const sibNode = nodes.find((n) => n.column === "sibling");
              return sibNode ? (
                <text
                  x={sibNode.x}
                  y={height - 8}
                  textAnchor="middle"
                  style={{
                    fontFamily: "var(--font-inter), sans-serif",
                    fontSize: 10,
                    fill: "var(--color-ink-muted)",
                    fontStyle: "italic",
                  }}
                >
                  +{overflowSiblings} more siblings
                </text>
              ) : null;
            })()}
            {overflowChildren > 0 && (() => {
              const childNode = nodes.find((n) => n.column === "child");
              return childNode ? (
                <text
                  x={childNode.x}
                  y={height - 8}
                  textAnchor="middle"
                  style={{
                    fontFamily: "var(--font-inter), sans-serif",
                    fontSize: 10,
                    fill: "var(--color-ink-muted)",
                    fontStyle: "italic",
                  }}
                >
                  +{overflowChildren} more children
                </text>
              ) : null;
            })()}
          </motion.g>
        </AnimatePresence>

        {/* Ripple effect — outside the keyed group so it persists across transitions */}
        <AnimatePresence>
          {ripple && (
            <motion.circle
              key={ripple.key}
              cx={ripple.x}
              cy={ripple.y}
              fill="none"
              stroke="var(--clade-branch-active)"
              strokeWidth={2}
              initial={{ r: 6, opacity: 0.6 }}
              animate={{ r: 60, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              onAnimationComplete={() => setRipple(null)}
            />
          )}
        </AnimatePresence>
      </svg>
    </div>
  );
}

function BranchPathElement({
  path,
  delay,
}: {
  path: BranchPath;
  delay: number;
}) {
  return (
    <motion.path
      d={path.d}
      fill="none"
      stroke={path.isActive ? "var(--clade-branch-active)" : "var(--clade-branch)"}
      strokeWidth={path.width}
      strokeLinecap="round"
      opacity={path.isActive ? 1 : 0.6}
      initial={{ pathLength: 0, opacity: 0 }}
      animate={{ pathLength: 1, opacity: path.isActive ? 1 : 0.6 }}
      transition={{
        pathLength: { duration: 0.4, delay, ease: "easeInOut" },
        opacity: { duration: 0.2, delay },
      }}
    />
  );
}
