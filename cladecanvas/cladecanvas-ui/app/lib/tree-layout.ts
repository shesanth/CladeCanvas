import type { TreeNode } from "./api";

export type LayoutNode = {
  node: TreeNode;
  x: number;
  y: number;
  column: "parent" | "sibling" | "selected" | "child";
  isSelected: boolean;
};

export type CladogramLayout = {
  nodes: LayoutNode[];
  paths: BranchPath[];
  width: number;
  height: number;
  overflowSiblings: number;
  overflowChildren: number;
};

export type BranchPath = {
  d: string;
  width: number;
  isActive: boolean;
  fromId: string;
  toId: string;
};

// Layout constants
const ROW_HEIGHT = 56;
const PADDING_Y = 40;
const PADDING_X = 30;
const MAX_SIBLINGS = 8;
const MAX_CHILDREN = 10;
const COL_GAP = 280; // horizontal gap between columns

function generateBezierPath(x1: number, y1: number, x2: number, y2: number): string {
  const midX = (x1 + x2) / 2;
  return `M ${x1},${y1} C ${midX},${y1} ${midX},${y2} ${x2},${y2}`;
}

export function branchWidth(numTips: number | null | undefined): number {
  if (!numTips || numTips <= 1) return 1.5;
  return Math.min(1.5 + Math.log10(numTips) * 1.2, 8);
}

export function computeLayout(
  parent: TreeNode | null,
  siblings: TreeNode[],
  selected: TreeNode,
  children: TreeNode[]
): CladogramLayout {
  const nodes: LayoutNode[] = [];
  const paths: BranchPath[] = [];

  // Truncation
  const overflowSiblings = Math.max(0, siblings.length - MAX_SIBLINGS);
  const overflowChildren = Math.max(0, children.length - MAX_CHILDREN);
  const visibleSiblings = siblings.slice(0, MAX_SIBLINGS);
  const visibleChildren = children.slice(0, MAX_CHILDREN);

  const hasChildren = visibleChildren.length > 0;

  // Determine column x positions based on what's present
  // 3-col: parent | siblings+selected | children
  // 2-col no parent (root): selected | children
  // 2-col no children (leaf): parent | siblings+selected
  const colCount = (parent ? 1 : 0) + 1 + (hasChildren ? 1 : 0);
  let colParentX: number;
  let colMidX: number;
  let colChildX: number;

  if (colCount === 3) {
    colParentX = PADDING_X + 80;
    colMidX = colParentX + COL_GAP;
    colChildX = colMidX + COL_GAP;
  } else if (!parent) {
    // Root: no parent column
    colParentX = 0; // unused
    colMidX = PADDING_X + 80;
    colChildX = colMidX + COL_GAP;
  } else {
    // Leaf: no children column
    colParentX = PADDING_X + 80;
    colMidX = colParentX + COL_GAP;
    colChildX = 0; // unused
  }

  // Place siblings above selected, selected in the middle, forming the mid column
  // Selected is placed so siblings fan above and it sits at the center/bottom
  const sibCount = visibleSiblings.length;
  const childCount = visibleChildren.length;

  // The mid column has sibCount + 1 (selected) items
  // Place selected so both sibling fan and child fan are roughly centered
  // Selected Y is the anchor point — center it vertically considering both fans
  const sibFanHeight = sibCount * ROW_HEIGHT;
  const childFanHeight = childCount > 0 ? (childCount - 1) * ROW_HEIGHT : 0;
  const maxFanAbove = Math.max(sibFanHeight, childFanHeight / 2);

  const selectedY = PADDING_Y + maxFanAbove + ROW_HEIGHT / 2;

  // Parent: aligned with selected
  if (parent) {
    nodes.push({
      node: parent,
      x: colParentX,
      y: selectedY,
      column: "parent",
      isSelected: false,
    });
  }

  // Siblings: fan upward from selected position
  for (let i = 0; i < sibCount; i++) {
    const ny = selectedY - (sibCount - i) * ROW_HEIGHT;
    nodes.push({
      node: visibleSiblings[i],
      x: colMidX,
      y: ny,
      column: "sibling",
      isSelected: false,
    });
  }

  // Selected node
  nodes.push({
    node: selected,
    x: colMidX,
    y: selectedY,
    column: "selected",
    isSelected: true,
  });

  // Children: fan out centered on selectedY
  const childStartY = selectedY - childFanHeight / 2;
  for (let i = 0; i < childCount; i++) {
    const ny = childStartY + i * ROW_HEIGHT;
    nodes.push({
      node: visibleChildren[i],
      x: colChildX,
      y: ny,
      column: "child",
      isSelected: false,
    });
  }

  // Generate all paths from final node positions
  const nodeMap = new Map(nodes.map((n) => [n.node.node_id, n]));

  if (parent) {
    const pn = nodeMap.get(parent.node_id)!;
    for (const n of nodes) {
      if (n.column === "sibling" || n.column === "selected") {
        paths.push({
          d: generateBezierPath(pn.x, pn.y, n.x, n.y),
          width: branchWidth(n.node.num_tips),
          isActive: n.isSelected,
          fromId: parent.node_id,
          toId: n.node.node_id,
        });
      }
    }
  }

  const sn = nodeMap.get(selected.node_id)!;
  for (const n of nodes) {
    if (n.column === "child") {
      paths.push({
        d: generateBezierPath(sn.x, sn.y, n.x, n.y),
        width: branchWidth(n.node.num_tips),
        isActive: false,
        fromId: selected.node_id,
        toId: n.node.node_id,
      });
    }
  }

  // Compute bounds
  const allY = nodes.map((n) => n.y);
  const allX = nodes.map((n) => n.x);
  const minY = Math.min(...allY);
  const maxX = Math.max(...allX);

  // Normalize: shift everything so min Y has padding
  const yOffset = PADDING_Y - minY + ROW_HEIGHT / 2;
  if (yOffset !== 0) {
    for (const n of nodes) n.y += yOffset;
    // Regenerate paths with corrected positions
    paths.length = 0;
    if (parent) {
      const pn = nodeMap.get(parent.node_id)!;
      for (const n of nodes) {
        if (n.column === "sibling" || n.column === "selected") {
          paths.push({
            d: generateBezierPath(pn.x, pn.y, n.x, n.y),
            width: branchWidth(n.node.num_tips),
            isActive: n.isSelected,
            fromId: parent.node_id,
            toId: n.node.node_id,
          });
        }
      }
    }
    const sn2 = nodeMap.get(selected.node_id)!;
    for (const n of nodes) {
      if (n.column === "child") {
        paths.push({
          d: generateBezierPath(sn2.x, sn2.y, n.x, n.y),
          width: branchWidth(n.node.num_tips),
          isActive: false,
          fromId: selected.node_id,
          toId: n.node.node_id,
        });
      }
    }
  }

  const finalMaxY = Math.max(...nodes.map((n) => n.y));
  const height = finalMaxY + PADDING_Y + ROW_HEIGHT / 2;
  const width = maxX + PADDING_X + 160; // extra space for labels

  return {
    nodes,
    paths,
    width: Math.max(width, 400),
    height: Math.max(height, 200),
    overflowSiblings,
    overflowChildren,
  };
}
