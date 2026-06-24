"use client";

import { motion } from "framer-motion";
import type { TreeNode } from "../lib/api";
import type { LabelSide } from "../lib/tree-layout";

type Props = {
  node: TreeNode;
  x: number;
  y: number;
  isSelected: boolean;
  column: "parent" | "sibling" | "selected" | "child";
  onClick: () => void;
  animationDelay?: number;
  compact?: boolean;
  vertical?: boolean;
  labelSide?: LabelSide;
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
  compact = false,
  vertical = false,
  labelSide,
}: Props) {
  const radius = isSelected ? SELECTED_RADIUS : NODE_RADIUS;
  const resolvedLabelSide = labelSide ?? (column === "parent" || column === "sibling" ? "left" : "right");
  const labelAnchor =
    resolvedLabelSide === "center" ? "middle" : resolvedLabelSide === "left" ? "end" : "start";
  const labelDx =
    resolvedLabelSide === "center" ? 0 : resolvedLabelSide === "left" ? -(radius + 8) : radius + 8;
  const centerLabelAbove = vertical && resolvedLabelSide === "center" && column === "parent";
  const labelY = centerLabelAbove ? y - 16 : y - 4;
  const speciesY = centerLabelAbove ? y - 3 : y + 12;
  const displayName = node.display_name || node.name;
  const maxLabelChars = compact ? (isSelected ? 16 : 15) : 20;
  const label =
    displayName.length > maxLabelChars
      ? displayName.slice(0, maxLabelChars - 2) + "..."
      : displayName;

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
      <circle cx={x} cy={y} r={Math.max(radius + 8, 20)} fill="transparent" />

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

      <motion.circle
        cx={x}
        cy={y}
        r={radius}
        fill="var(--clade-node-dot)"
        whileHover={{ scale: 1.15 }}
        transition={{ duration: 0.15 }}
      />

      <text
        x={x + labelDx}
        y={labelY}
        textAnchor={labelAnchor}
        style={{
          fontFamily: "var(--font-playfair), serif",
          fontStyle: "italic",
          fontSize: isSelected ? (compact ? 12 : 13) : compact ? 10 : 11,
          fontWeight: isSelected ? 600 : 400,
          fill: isSelected ? "var(--color-ink)" : "var(--clade-branch)",
        }}
      >
        {label}
      </text>

      {node.num_tips != null && (
        <text
          x={x + labelDx}
          y={speciesY}
          textAnchor={labelAnchor}
          style={{
            fontFamily: "var(--font-inter), sans-serif",
            fontSize: compact ? 8 : 9,
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
