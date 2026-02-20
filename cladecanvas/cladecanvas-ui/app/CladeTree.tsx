"use client";

import React, { useEffect, useState, useRef } from "react";

export type TreeNode = {
  name: string;
  node_id: string;
  ott_id?: number | null;
  child_count?: number | null;
  has_metadata?: boolean | null;
  rank?: string | null;
  num_tips?: number | null;
  display_name?: string | null;
};

type Props = {
  api: string;
  onSelect: (node: TreeNode) => void;
  activeNodeId: string | null;
  rootNodeId: string;
};

export default function CladeTree({ api, onSelect, activeNodeId, rootNodeId }: Props) {
  type TreeNodeWithChildren = TreeNode & { children?: TreeNodeWithChildren[] };

  const [tree, setTree] = useState<TreeNodeWithChildren | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const asideRef = useRef<HTMLDivElement>(null);
  const treeRef = useRef<TreeNodeWithChildren | null>(null);

  // Keep ref in sync so toggleExpand never has a stale closure
  treeRef.current = tree;

  useEffect(() => {
    if (!activeNodeId || !asideRef.current) return;
    requestAnimationFrame(() => {
      const aside = asideRef.current;
      const el = aside?.querySelector(`[data-node-id="${activeNodeId}"]`);
      if (el && aside) {
        const asideRect = aside.getBoundingClientRect();
        const elRect = el.getBoundingClientRect();
        const targetTop = aside.scrollTop + (elRect.top - asideRect.top) - asideRect.height / 2;
        const targetLeft = aside.scrollLeft + (elRect.left - asideRect.left) - 16;
        aside.scrollTo({ top: targetTop, left: targetLeft, behavior: "smooth" });
      }
    });
  }, [activeNodeId, tree]);

  const RANK_PRIORITY: Record<string, number> = {
    kingdom: 1000,
    phylum: 800,
    class: 600,
    order: 500,
    family: 400,
    genus: 300,
    species: 200,
    clade: 900,
  };

  const isSynthetic = (n: TreeNode) => n.node_id.startsWith("mrcaott");

  const score = (n: TreeNode) => {
    const metadataScore = n.has_metadata ? 100 : 0;
    const childScore = typeof n.child_count === "number" ? n.child_count : 0;
    const rankBoost = n.rank ? (RANK_PRIORITY[n.rank.toLowerCase()] ?? 0) : 0;
    const tipsBoost = n.num_tips ? Math.log10(n.num_tips) * 100 : 0;
    return metadataScore + childScore + rankBoost + tipsBoost;
  };

  useEffect(() => {
    if (!rootNodeId) return;

    const loadTree = async () => {
      try {
        const nodeRes = await fetch(`${api}/node/${rootNodeId}`);
        if (!nodeRes.ok) throw new Error("Failed to fetch node");
        const node: TreeNode = await nodeRes.json();

        const childrenRes = await fetch(`${api}/tree/children/${rootNodeId}`);
        if (!childrenRes.ok) throw new Error("Failed to fetch children");
        const children: TreeNode[] = await childrenRes.json();

        const clean = (n: TreeNode) =>
          typeof n.name === "string" &&
          !n.name.toLowerCase().includes("environmental") &&
          n.num_tips != null;

        const filtered = children.filter(clean);
        const topChildren = (filtered.length > 0 ? filtered : children)
          .sort((a, b) => score(b) - score(a))
          .slice(0, 100);

        setTree({ ...node, children: topChildren });
        setExpanded({ [node.node_id]: true });
      } catch (err) {
        console.error("loadTree error", err);
        setTree(null);
      }
    };

    loadTree();
  }, [api, rootNodeId]);

  const toggleExpand = async (node: TreeNodeWithChildren) => {
    const isOpen = expanded[node.node_id];
    if (isOpen) {
      setExpanded((prev) => ({ ...prev, [node.node_id]: false }));
      return;
    }

    try {
      const res = await fetch(`${api}/tree/children/${node.node_id}`);
      if (!res.ok) return;
      const children: TreeNode[] = await res.json();

      const clean = (n: TreeNode) =>
        typeof n.name === "string" &&
        !n.name.toLowerCase().includes("environmental");

      const filtered = children.filter(clean);
      const topChildren = (filtered.length > 0 ? filtered : children)
        .sort((a, b) => score(b) - score(a))
        .slice(0, 100);

      node.children = topChildren;
      // Use ref to avoid stale closure — always spread from latest tree
      setTree({ ...treeRef.current! });
    } catch (err) {
      console.error("toggleExpand error", err);
      return;
    }

    setExpanded((prev) => ({ ...prev, [node.node_id]: true }));
  };

  const renderTree = (node: TreeNodeWithChildren): React.ReactNode => (
    <div key={node.node_id} className="pl-2">
      <button
        data-node-id={node.node_id}
        onClick={() => {
          onSelect(node);
          toggleExpand(node);
        }}
        className={`text-left text-sm py-0.5 whitespace-nowrap ${
          node.node_id === activeNodeId ? "font-bold text-highlight" : ""
        } ${isSynthetic(node) && !node.display_name ? "italic text-gray-400" : ""}`}
      >
        {node.display_name || node.name}
      </button>
      {expanded[node.node_id] && node.children && (
        <div className="pl-4 border-l border-gray-300 ml-1">
          {node.children.map((child) => renderTree(child))}
        </div>
      )}
    </div>
  );

  return (
    <aside ref={asideRef} className="w-64 overflow-auto border-r border-softgray p-2 text-sm sticky top-4 max-h-[50vh]">
      <div className="min-h-[25vh]" aria-hidden="true" />
      {tree ? renderTree(tree) : <div className="text-sm p-2">Loading tree...</div>}
      <div className="min-h-[25vh]" aria-hidden="true" />
    </aside>
  );
}
