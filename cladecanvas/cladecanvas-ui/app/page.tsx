"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  fetchNode,
  fetchMetadata,
  fetchChildren,
  fetchLineage,
  type TreeNode,
  type Metadata,
} from "./lib/api";
import { topByScore } from "./lib/scoring";
import SearchBar from "./components/SearchBar";
import Breadcrumb from "./components/Breadcrumb";
import LocalCladogram from "./components/LocalCladogram";
import ReaderPanel from "./components/ReaderPanel";
import ChildrenCards from "./components/ChildrenCards";

const DEFAULT_ROOT = "ott691846"; // Metazoa

export default function Page() {
  const [selectedNodeId, setSelectedNodeId] = useState(DEFAULT_ROOT);
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [lineage, setLineage] = useState<TreeNode[]>([]);
  const [parent, setParent] = useState<TreeNode | null>(null);
  const [siblings, setSiblings] = useState<TreeNode[]>([]);
  const [children, setChildren] = useState<TreeNode[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const abortRef = useRef<AbortController | null>(null);

  const loadNode = useCallback(async (nodeId: string) => {
    // Cancel in-flight metadata request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setSelectedNodeId(nodeId);

    try {
      // Phase 1: parallel fetches for the selected node
      const [node, meta, lin, kids] = await Promise.all([
        fetchNode(nodeId).catch(() => null),
        fetchMetadata(nodeId, controller.signal).catch(() => null),
        fetchLineage(nodeId).catch(() => [] as TreeNode[]),
        fetchChildren(nodeId).catch(() => [] as TreeNode[]),
      ]);

      if (controller.signal.aborted) return;
      if (!node) {
        // API unreachable — bail gracefully
        setIsLoading(false);
        return;
      }

      setSelectedNode(node);
      setMetadata(meta);
      setLineage(lin);
      setChildren(topByScore(kids, 100));

      // Phase 2: get parent and siblings from lineage
      const parentNode =
        lin.length >= 2 ? lin[lin.length - 2] : null;
      setParent(parentNode);

      if (parentNode) {
        const parentKids = await fetchChildren(parentNode.node_id).catch(
          () => [] as TreeNode[]
        );
        if (controller.signal.aborted) return;
        // Siblings = parent's children minus selected and parent itself
        const sibs = topByScore(
          parentKids.filter(
            (c) => c.node_id !== nodeId && c.node_id !== parentNode.node_id
          ),
          100
        );
        setSiblings(sibs);
      } else {
        setSiblings([]);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      console.error("loadNode error:", err);
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadNode(DEFAULT_ROOT);
  }, [loadNode]);

  const onSelectNode = useCallback(
    (nodeId: string) => {
      if (nodeId === selectedNodeId) return;
      loadNode(nodeId);
    },
    [selectedNodeId, loadNode]
  );

  return (
    <main
      className="max-w-4xl mx-auto px-4 md:px-6 py-6 md:py-8 min-h-screen"
      style={{ color: "var(--color-ink)" }}
    >
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <h1
          className="text-3xl font-bold tracking-tight"
          style={{ fontFamily: "var(--font-playfair), serif" }}
        >
          CladeCanvas
        </h1>
        <SearchBar onSelect={onSelectNode} />
      </header>

      {/* Breadcrumb */}
      <Breadcrumb lineage={lineage} onSelect={onSelectNode} />

      {/* Cladogram */}
      {selectedNode && (
        <LocalCladogram
          parent={parent}
          siblings={siblings}
          selected={selectedNode}
          childNodes={children}
          onSelect={onSelectNode}
        />
      )}

      {/* Loading skeleton */}
      {isLoading && !selectedNode && (
        <div className="space-y-4 my-8">
          <div className="skeleton h-[300px] w-full rounded-xl" />
          <div className="skeleton h-8 w-48 mt-6" />
          <div className="skeleton h-4 w-full mt-2" />
          <div className="skeleton h-4 w-3/4 mt-1" />
          <div className="skeleton h-4 w-1/2 mt-1" />
        </div>
      )}

      {/* Reader Panel */}
      <ReaderPanel metadata={metadata} node={selectedNode}>
        <ChildrenCards nodes={children} onSelect={onSelectNode} />
      </ReaderPanel>
    </main>
  );
}
