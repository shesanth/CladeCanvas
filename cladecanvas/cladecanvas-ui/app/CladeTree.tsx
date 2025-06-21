"use client";

import React, { useEffect, useState } from "react";

export type TreeNode = {
  name: string;
  ott_id: number;
  child_count?: number | null;
  has_metadata?: boolean | null;
  rank?: string | null;
};

type Props = {
  api: string;
  onSelect: (node: TreeNode) => void;
  activeOttId: number | null;
  rootOttId: number;
};

export default function CladeTree({ api, onSelect, activeOttId, rootOttId }: Props) {
  const [tree, setTree] = useState<TreeNodeWithChildren | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  type TreeNodeWithChildren = TreeNode & { children?: TreeNodeWithChildren[] };

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

  const PRIORITY_OTT_IDS = new Set([
    641038, // Eumetazoa, doesn't have official rank but is a major clade
  ]);

  const score = (n: TreeNode) => {
    const metadataScore = n.has_metadata ? 100 : 0;
    const childScore = typeof n.child_count === "number" ? n.child_count : 0;
    const rankBoost = n.rank ? (RANK_PRIORITY[n.rank.toLowerCase()] ?? 0) : 0;
    const priorityBoost = PRIORITY_OTT_IDS.has(n.ott_id) ? 10000 : 0;
    return metadataScore + childScore + rankBoost + priorityBoost;
  };

  useEffect(() => {
    if (!rootOttId) return;

    const loadTree = async () => {
      try {
        const nodeRes = await fetch(`${api}/node/${rootOttId}`);
        if (!nodeRes.ok) throw new Error("Failed to fetch node");
        const node: TreeNode = await nodeRes.json();

        const childrenRes = await fetch(`${api}/tree/children/${rootOttId}`);
        if (!childrenRes.ok) throw new Error("Failed to fetch children");
        const children: TreeNode[] = await childrenRes.json();

        const clean = (n: TreeNode) =>
          typeof n.name === "string" &&
          !n.name.toLowerCase().includes("environmental");

        const filtered = children.filter(clean);
        const topChildren = (filtered.length > 0 ? filtered : children)
          .sort((a, b) => score(b) - score(a))
          .slice(0, 100);

        setTree({ ...node, children: topChildren });
        setExpanded({ [node.ott_id]: true });
      } catch (err) {
        console.error("loadTree error", err);
        setTree(null);
      }
    };

    loadTree();
  }, [api, rootOttId]);

  const toggleExpand = async (node: TreeNodeWithChildren) => {
    const isOpen = expanded[node.ott_id];
    if (isOpen) {
      setExpanded((prev) => ({ ...prev, [node.ott_id]: false }));
      return;
    }

    try {
      const res = await fetch(`${api}/tree/children/${node.ott_id}`);
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
      setTree({ ...tree! });
    } catch (err) {
      console.error("toggleExpand error", err);
      return;
    }

    setExpanded((prev) => ({ ...prev, [node.ott_id]: true }));
  };

  const renderTree = (node: TreeNodeWithChildren): React.ReactNode => (
    <div key={node.ott_id} className="pl-2">
      <button
        onClick={() => {
          onSelect(node);
          toggleExpand(node);
        }}
        className={`text-left text-sm py-0.5 w-full truncate ${
          node.ott_id === activeOttId ? "font-bold text-highlight" : ""
        }`}
      >
        {node.name}
      </button>
      {expanded[node.ott_id] && node.children && (
        <div className="pl-4 border-l border-gray-300 ml-1">
          {node.children.map((child) => renderTree(child))}
        </div>
      )}
    </div>
  );

  return (
    <aside className="w-64 overflow-y-auto border-r border-softgray p-2 text-sm">
      {tree ? renderTree(tree) : <div className="text-sm p-2">Loading tree...</div>}
    </aside>
  );
}
