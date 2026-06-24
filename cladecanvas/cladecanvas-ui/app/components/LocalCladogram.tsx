"use client";

import {
  useState,
  useCallback,
  useEffect,
  useRef,
  type KeyboardEvent,
} from "react";
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

type DisplayMode = "full" | "compact" | "vertical";

function getDisplayMode(): DisplayMode {
  if (typeof window === "undefined") return "full";
  const isPhoneWidth = window.matchMedia("(max-width: 639px)").matches;
  const isPortrait = window.matchMedia("(orientation: portrait)").matches;
  const isShortLandscape =
    window.matchMedia("(max-height: 479px)").matches && !isPortrait;

  if (isPhoneWidth && isPortrait) return "vertical";
  if (isPhoneWidth || isShortLandscape) return "compact";
  return "full";
}

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
  const [displayMode, setDisplayMode] = useState<DisplayMode>(getDisplayMode);
  const [showAllChildren, setShowAllChildren] = useState(false);
  const [showAllSiblings, setShowAllSiblings] = useState(false);

  useEffect(() => {
    setShowAllChildren(false);
    setShowAllSiblings(false);
  }, [selected.node_id]);

  useEffect(() => {
    const phoneMedia = window.matchMedia("(max-width: 639px)");
    const portraitMedia = window.matchMedia("(orientation: portrait)");
    const shortMedia = window.matchMedia("(max-height: 479px)");
    const update = () => setDisplayMode(getDisplayMode());
    update();
    phoneMedia.addEventListener("change", update);
    portraitMedia.addEventListener("change", update);
    shortMedia.addEventListener("change", update);
    window.addEventListener("resize", update);
    return () => {
      phoneMedia.removeEventListener("change", update);
      portraitMedia.removeEventListener("change", update);
      shortMedia.removeEventListener("change", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  const isVertical = displayMode === "vertical";
  const isCompact = displayMode !== "full";
  const layout = computeLayout(parent, siblings, selected, childNodes, {
    compact: isCompact,
    orientation: isVertical ? "vertical" : "horizontal",
    maxChildren: showAllChildren ? childNodes.length : undefined,
    maxSiblings: showAllSiblings ? siblings.length : undefined,
  });
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

  const handleShowAllChildren = useCallback(() => {
    setShowAllChildren(true);
  }, []);

  const handleShowAllSiblings = useCallback(() => {
    setShowAllSiblings(true);
  }, []);

  const handleOverflowKeyDown = useCallback(
    (event: KeyboardEvent<SVGGElement>, showAll: () => void) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        showAll();
      }
    },
    []
  );

  const svgHeight = Math.max(height, isVertical ? 220 : isCompact ? 180 : 200);

  return (
    <div
      className="w-[calc(100%+1.5rem)] -mx-3 sm:mx-auto sm:w-full max-w-4xl overflow-x-auto my-3 sm:my-4 rounded-none sm:rounded-xl touch-pan-x"
      data-cladogram-mode={displayMode}
      style={{ background: "var(--color-paper-light)" }}
    >
      <svg
        width={width}
        height={svgHeight}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        className={isVertical ? "block mx-auto" : "block"}
      >
        <AnimatePresence>
          <motion.g
            key={`${selected.node_id}-${displayMode}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {paths.map((path, idx) => (
              <BranchPathElement
                key={`${path.fromId}-${path.toId}`}
                path={path}
                delay={0.05 * idx}
              />
            ))}

            {nodes.map((layoutNode, idx) => (
              <CladogramNode
                key={`${layoutNode.column}-${layoutNode.node.node_id}`}
                node={layoutNode.node}
                x={layoutNode.x}
                y={layoutNode.y}
                isSelected={layoutNode.isSelected}
                column={layoutNode.column}
                compact={isCompact}
                vertical={isVertical}
                labelSide={layoutNode.labelSide}
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

            {overflowSiblings > 0 && (() => {
              const sibNode = nodes.find((n) => n.column === "sibling");
              return sibNode ? (
                <g
                  role="button"
                  tabIndex={0}
                  aria-label={`Show ${overflowSiblings} more siblings`}
                  onClick={handleShowAllSiblings}
                  onKeyDown={(event) =>
                    handleOverflowKeyDown(event, handleShowAllSiblings)
                  }
                >
                  <text
                    x={sibNode.x}
                    y={height - 8}
                    textAnchor="middle"
                    style={{
                      cursor: "pointer",
                      fontFamily: "var(--font-inter), sans-serif",
                      fontSize: isCompact ? 9 : 10,
                      fill: "var(--color-ink-muted)",
                      fontStyle: "italic",
                      textDecoration: "underline",
                    }}
                  >
                    +{overflowSiblings} more siblings
                  </text>
                </g>
              ) : null;
            })()}
            {overflowChildren > 0 && (() => {
              const childNode = nodes.find((n) => n.column === "child");
              return childNode ? (
                <g
                  role="button"
                  tabIndex={0}
                  aria-label={`Show ${overflowChildren} more children`}
                  onClick={handleShowAllChildren}
                  onKeyDown={(event) =>
                    handleOverflowKeyDown(event, handleShowAllChildren)
                  }
                >
                  <text
                    x={childNode.x}
                    y={height - 8}
                    textAnchor="middle"
                    style={{
                      cursor: "pointer",
                      fontFamily: "var(--font-inter), sans-serif",
                      fontSize: isCompact ? 9 : 10,
                      fill: "var(--color-ink-muted)",
                      fontStyle: "italic",
                      textDecoration: "underline",
                    }}
                  >
                    +{overflowChildren} more children
                  </text>
                </g>
              ) : null;
            })()}
          </motion.g>
        </AnimatePresence>

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
