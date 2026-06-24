import type { TreeNode } from "./api";

export type LabelSide = "left" | "right" | "center";

export type LayoutNode = {
  node: TreeNode;
  x: number;
  y: number;
  column: "parent" | "sibling" | "selected" | "child";
  isSelected: boolean;
  labelSide: LabelSide;
};

export type CladogramLayout = {
  nodes: LayoutNode[];
  paths: BranchPath[];
  width: number;
  height: number;
  overflowSiblings: number;
  overflowChildren: number;
  orientation: "horizontal" | "vertical";
};

export type BranchPath = {
  d: string;
  width: number;
  isActive: boolean;
  fromId: string;
  toId: string;
};

type LayoutOptions = {
  compact?: boolean;
  orientation?: "horizontal" | "vertical";
  maxSiblings?: number;
  maxChildren?: number;
};

function horizontalConstants(compact: boolean) {
  return {
    rowHeight: compact ? 46 : 56,
    paddingY: compact ? 24 : 40,
    paddingX: compact ? 12 : 30,
    parentLabelRoom: compact ? 58 : 80,
    labelRoom: compact ? 82 : 160,
    maxSiblings: compact ? 3 : 8,
    maxChildren: compact ? 5 : 10,
    colGap: compact ? 100 : 280,
  };
}

function verticalConstants() {
  return {
    width: 320,
    centerX: 160,
    paddingY: 24,
    parentY: 42,
    siblingY: 104,
    selectedYWithParent: 158,
    selectedYRoot: 56,
    childGapY: 92,
    childRowGap: 54,
    siblingGap: 86,
    childGapX: 60,
    maxSiblings: 0,
    maxChildren: 5,
  };
}

function generatePath(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  orientation: "horizontal" | "vertical"
): string {
  if (orientation === "vertical") {
    const midY = (y1 + y2) / 2;
    return `M ${x1},${y1} C ${x1},${midY} ${x2},${midY} ${x2},${y2}`;
  }

  const midX = (x1 + x2) / 2;
  return `M ${x1},${y1} C ${midX},${y1} ${midX},${y2} ${x2},${y2}`;
}

export function branchWidth(numTips: number | null | undefined): number {
  if (!numTips || numTips <= 1) return 1.5;
  return Math.min(1.5 + Math.log10(numTips) * 1.2, 8);
}

function centeredPositions(count: number, center: number, gap: number): number[] {
  if (count <= 0) return [];
  const start = center - ((count - 1) * gap) / 2;
  return Array.from({ length: count }, (_, index) => start + index * gap);
}

function labelSideForX(x: number, width: number): LabelSide {
  if (x < width * 0.35) return "right";
  if (x > width * 0.65) return "left";
  return "right";
}

function computeVerticalLayout(
  parent: TreeNode | null,
  siblings: TreeNode[],
  selected: TreeNode,
  children: TreeNode[],
  options: LayoutOptions = {}
): CladogramLayout {
  const {
    width,
    centerX,
    paddingY,
    parentY,
    siblingY,
    selectedYWithParent,
    selectedYRoot,
    childGapY,
    childRowGap,
    siblingGap,
    childGapX,
    maxSiblings: defaultMaxSiblings,
    maxChildren: defaultMaxChildren,
  } = verticalConstants();
  const maxSiblings = options.maxSiblings ?? defaultMaxSiblings;
  const maxChildren = options.maxChildren ?? defaultMaxChildren;
  const nodes: LayoutNode[] = [];
  const paths: BranchPath[] = [];
  const visibleSiblings = siblings.slice(0, maxSiblings);
  const visibleChildren = children.slice(0, maxChildren);
  const overflowSiblings = Math.max(0, siblings.length - maxSiblings);
  const overflowChildren = Math.max(0, children.length - maxChildren);
  const selectedY = parent ? selectedYWithParent : selectedYRoot;

  if (parent) {
    nodes.push({
      node: parent,
      x: centerX,
      y: parentY,
      column: "parent",
      isSelected: false,
      labelSide: "center",
    });

    const siblingXs = centeredPositions(visibleSiblings.length, centerX, siblingGap);
    visibleSiblings.forEach((node, index) => {
      const x = siblingXs[index];
      nodes.push({
        node,
        x,
        y: siblingY,
        column: "sibling",
        isSelected: false,
        labelSide: labelSideForX(x, width),
      });
    });
  }

  nodes.push({
    node: selected,
    x: centerX,
    y: selectedY,
    column: "selected",
    isSelected: true,
    labelSide: "right",
  });

  const childStartY = selectedY + childGapY;
  const childXs = centeredPositions(visibleChildren.length, centerX, childGapX);
  visibleChildren.forEach((node, index) => {
    const x = childXs[index];
    nodes.push({
      node,
      x,
      y: childStartY + index * childRowGap,
      column: "child",
      isSelected: false,
      labelSide: labelSideForX(x, width),
    });
  });

  const nodeMap = new Map(nodes.map((node) => [node.node.node_id, node]));
  if (parent) {
    const parentNode = nodeMap.get(parent.node_id)!;
    for (const node of nodes) {
      if (node.column === "sibling" || node.column === "selected") {
        paths.push({
          d: generatePath(parentNode.x, parentNode.y, node.x, node.y, "vertical"),
          width: branchWidth(node.node.num_tips),
          isActive: node.isSelected,
          fromId: parent.node_id,
          toId: node.node.node_id,
        });
      }
    }
  }

  const selectedNode = nodeMap.get(selected.node_id)!;
  for (const node of nodes) {
    if (node.column === "child") {
      paths.push({
        d: generatePath(selectedNode.x, selectedNode.y, node.x, node.y, "vertical"),
        width: branchWidth(node.node.num_tips),
        isActive: false,
        fromId: selected.node_id,
        toId: node.node.node_id,
      });
    }
  }

  const maxY = Math.max(...nodes.map((node) => node.y));
  const height = Math.max(maxY + paddingY + 42, 220);

  return {
    nodes,
    paths,
    width,
    height,
    overflowSiblings,
    overflowChildren,
    orientation: "vertical",
  };
}

function computeHorizontalLayout(
  parent: TreeNode | null,
  siblings: TreeNode[],
  selected: TreeNode,
  children: TreeNode[],
  compact: boolean,
  options: LayoutOptions = {}
): CladogramLayout {
  const {
    rowHeight,
    paddingY,
    paddingX,
    parentLabelRoom,
    labelRoom,
    maxSiblings: defaultMaxSiblings,
    maxChildren: defaultMaxChildren,
    colGap,
  } = horizontalConstants(compact);
  const maxSiblings = options.maxSiblings ?? defaultMaxSiblings;
  const maxChildren = options.maxChildren ?? defaultMaxChildren;
  const nodes: LayoutNode[] = [];
  const paths: BranchPath[] = [];
  const overflowSiblings = Math.max(0, siblings.length - maxSiblings);
  const overflowChildren = Math.max(0, children.length - maxChildren);
  const visibleSiblings = siblings.slice(0, maxSiblings);
  const visibleChildren = children.slice(0, maxChildren);
  const hasChildren = visibleChildren.length > 0;
  const colCount = (parent ? 1 : 0) + 1 + (hasChildren ? 1 : 0);
  let colParentX: number;
  let colMidX: number;
  let colChildX: number;

  if (colCount === 3) {
    colParentX = paddingX + parentLabelRoom;
    colMidX = colParentX + colGap;
    colChildX = colMidX + colGap;
  } else if (!parent) {
    colParentX = 0;
    colMidX = paddingX + (compact ? 24 : parentLabelRoom);
    colChildX = colMidX + colGap;
  } else {
    colParentX = paddingX + parentLabelRoom;
    colMidX = colParentX + colGap;
    colChildX = 0;
  }

  const sibCount = visibleSiblings.length;
  const childCount = visibleChildren.length;
  const sibFanHeight = sibCount * rowHeight;
  const childFanHeight = childCount > 0 ? (childCount - 1) * rowHeight : 0;
  const maxFanAbove = Math.max(sibFanHeight, childFanHeight / 2);
  const selectedY = paddingY + maxFanAbove + rowHeight / 2;

  if (parent) {
    nodes.push({
      node: parent,
      x: colParentX,
      y: selectedY,
      column: "parent",
      isSelected: false,
      labelSide: "left",
    });
  }

  for (let i = 0; i < sibCount; i++) {
    nodes.push({
      node: visibleSiblings[i],
      x: colMidX,
      y: selectedY - (sibCount - i) * rowHeight,
      column: "sibling",
      isSelected: false,
      labelSide: "left",
    });
  }

  nodes.push({
    node: selected,
    x: colMidX,
    y: selectedY,
    column: "selected",
    isSelected: true,
    labelSide: "right",
  });

  const childStartY = selectedY - childFanHeight / 2;
  for (let i = 0; i < childCount; i++) {
    nodes.push({
      node: visibleChildren[i],
      x: colChildX,
      y: childStartY + i * rowHeight,
      column: "child",
      isSelected: false,
      labelSide: "right",
    });
  }

  const nodeMap = new Map(nodes.map((node) => [node.node.node_id, node]));
  const rebuildPaths = () => {
    paths.length = 0;
    if (parent) {
      const parentNode = nodeMap.get(parent.node_id)!;
      for (const node of nodes) {
        if (node.column === "sibling" || node.column === "selected") {
          paths.push({
            d: generatePath(parentNode.x, parentNode.y, node.x, node.y, "horizontal"),
            width: branchWidth(node.node.num_tips),
            isActive: node.isSelected,
            fromId: parent.node_id,
            toId: node.node.node_id,
          });
        }
      }
    }

    const selectedNode = nodeMap.get(selected.node_id)!;
    for (const node of nodes) {
      if (node.column === "child") {
        paths.push({
          d: generatePath(selectedNode.x, selectedNode.y, node.x, node.y, "horizontal"),
          width: branchWidth(node.node.num_tips),
          isActive: false,
          fromId: selected.node_id,
          toId: node.node.node_id,
        });
      }
    }
  };

  rebuildPaths();

  const minY = Math.min(...nodes.map((node) => node.y));
  const yOffset = paddingY - minY + rowHeight / 2;
  if (yOffset !== 0) {
    for (const node of nodes) node.y += yOffset;
    rebuildPaths();
  }

  const maxX = Math.max(...nodes.map((node) => node.x));
  const finalMaxY = Math.max(...nodes.map((node) => node.y));
  const height = finalMaxY + paddingY + rowHeight / 2;
  const width = maxX + paddingX + labelRoom;

  return {
    nodes,
    paths,
    width: Math.max(width, compact ? 320 : 400),
    height: Math.max(height, compact ? 180 : 200),
    overflowSiblings,
    overflowChildren,
    orientation: "horizontal",
  };
}

export function computeLayout(
  parent: TreeNode | null,
  siblings: TreeNode[],
  selected: TreeNode,
  children: TreeNode[],
  options: LayoutOptions = {}
): CladogramLayout {
  if (options.orientation === "vertical") {
    return computeVerticalLayout(parent, siblings, selected, children, options);
  }

  return computeHorizontalLayout(
    parent,
    siblings,
    selected,
    children,
    Boolean(options.compact),
    options
  );
}


