"use client";

import { motion } from "framer-motion";
import type { TreeNode } from "../lib/api";

type Props = {
  node: TreeNode;
  x: number;
  y: number;
  isSelected: boolean;
  column: "parent" | "sibling" | "selected" | "child";
  onClick: () => void;
  animationDelay?: number;
};

const NODE_RADIUS = 6;
const SELECTED_RADIUS = 10;

export default function CladogramNode({
  node,
  x,
  y,
  isSelected,
  column,
  onClick,
  animationDelay = 0,
}: Props) {
  const radius = isSelected ? SELECTED_RADIUS : NODE_RADIUS;

  // Label positioning: parent and sibling labels go LEFT, selected and children go RIGHT
  const labelsGoLeft = column === "parent" || column === "sibling";
  const labelAnchor = labelsGoLeft ? "end" : "start";
  const labelDx = labelsGoLeft ? -(radius + 8) : radius + 8;

  const displayName = node.display_name || node.name;

  return (
    <motion.g
      initial={{ opacity: 0, scale: 0.7 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{
        type: "spring",
        stiffness: 200,
        damping: 25,
        delay: animationDelay,
      }}
      style={{ cursor: "pointer" }}
      onClick={onClick}
    >
      {/* Hit area — larger invisible circle for easier clicking */}
      <circle cx={x} cy={y} r={Math.max(radius + 8, 20)} fill="transparent" />

      {/* Gold ring for selected node */}
      {isSelected && (
        <motion.circle
          cx={x}
          cy={y}
          r={radius + 3}
          fill="none"
          stroke="var(--clade-node-ring)"
          strokeWidth={2}
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: animationDelay + 0.1, duration: 0.3 }}
        />
      )}

      {/* Node circle */}
      <motion.circle
        cx={x}
        cy={y}
        r={radius}
        fill="var(--clade-node-dot)"
        whileHover={{ scale: 1.15 }}
        transition={{ duration: 0.15 }}
      />

      {/* Labels */}
      <text
        x={x + labelDx}
        y={y - 4}
        textAnchor={labelAnchor}
        style={{
          fontFamily: "var(--font-playfair), serif",
          fontStyle: "italic",
          fontSize: isSelected ? 13 : 11,
          fontWeight: isSelected ? 600 : 400,
          fill: isSelected ? "var(--color-ink)" : "var(--clade-branch)",
        }}
      >
        {displayName.length > 20 ? displayName.slice(0, 18) + "…" : displayName}
      </text>

      {/* Species count */}
      {node.num_tips != null && (
        <text
          x={x + labelDx}
          y={y + 12}
          textAnchor={labelAnchor}
          style={{
            fontFamily: "var(--font-inter), sans-serif",
            fontSize: 9,
            fill: "var(--color-ink-muted)",
            opacity: 0.7,
          }}
        >
          {node.num_tips.toLocaleString()} spp.
        </text>
      )}
    </motion.g>
  );
}
