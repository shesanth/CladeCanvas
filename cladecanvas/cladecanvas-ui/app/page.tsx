"use client";

import { Suspense, useState, useEffect, useRef, useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  fetchNode,
  fetchMetadata,
  fetchChildren,
  fetchLineage,
  fetchContextGraph,
  type ContextGraph,
  type NavigationMode,
  type TreeNode,
  type Metadata,
} from "./lib/api";
import { topByScore } from "./lib/scoring";
import SearchBar from "./components/SearchBar";
import Breadcrumb from "./components/Breadcrumb";
import LocalCladogram from "./components/LocalCladogram";
import ReaderPanel from "./components/ReaderPanel";
import ChildrenCards from "./components/ChildrenCards";
import ContextOverviewRail from "./components/ContextOverviewRail";
import JumpControls from "./components/JumpControls";

const DEFAULT_ROOT = "ott691846"; // Metazoa

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ExplorerPage />
    </Suspense>
  );
}

function ExplorerPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const nodeFromUrl = searchParams.get("node") || DEFAULT_ROOT;
  const navFromUrl: NavigationMode =
    searchParams.get("nav") === "overview" ? "overview" : "local";

  const [selectedNodeId, setSelectedNodeId] = useState(DEFAULT_ROOT);
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [lineage, setLineage] = useState<TreeNode[]>([]);
  const [contextGraph, setContextGraph] = useState<ContextGraph | null>(null);
  const [navigationMode, setNavigationMode] = useState<NavigationMode>("local");
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
    setContextGraph(null);

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
      fetchContextGraph(nodeId)
        .then((graph) => {
          if (!controller.signal.aborted) setContextGraph(graph);
        })
        .catch(() => {
          if (!controller.signal.aborted) setContextGraph(null);
        });

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

  useEffect(() => {
    setNavigationMode(navFromUrl);
    if (nodeFromUrl !== selectedNodeId || !selectedNode) {
      loadNode(nodeFromUrl);
    }
  }, [nodeFromUrl, navFromUrl, selectedNodeId, selectedNode, loadNode]);

  const updateUrl = useCallback(
    (nodeId: string, mode: NavigationMode = navigationMode) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("node", nodeId);
      params.set("nav", mode);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [navigationMode, pathname, router, searchParams]
  );

  const onSelectNode = useCallback(
    (nodeId: string) => {
      if (nodeId === selectedNodeId) return;
      updateUrl(nodeId);
    },
    [selectedNodeId, updateUrl]
  );

  const onModeChange = useCallback(
    (mode: NavigationMode) => {
      setNavigationMode(mode);
      updateUrl(selectedNodeId, mode);
    },
    [selectedNodeId, updateUrl]
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const tagName = target?.tagName;
      if (tagName === "INPUT" || tagName === "TEXTAREA" || target?.isContentEditable) {
        return;
      }

      if (event.key === "o") {
        event.preventDefault();
        onModeChange(navigationMode === "overview" ? "local" : "overview");
      } else if ((event.key === "ArrowUp" || event.key === "ArrowLeft") && parent) {
        event.preventDefault();
        onSelectNode(parent.node_id);
      } else if (event.key === "ArrowRight" && children[0]) {
        event.preventDefault();
        onSelectNode(children[0].node_id);
      } else if (event.key === "ArrowDown" && siblings[0]) {
        event.preventDefault();
        onSelectNode(siblings[0].node_id);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [children, navigationMode, onModeChange, onSelectNode, parent, siblings]);

  return (
    <main
      className="max-w-6xl mx-auto px-4 md:px-6 py-6 md:py-8 min-h-screen"
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

      <JumpControls
        mode={navigationMode}
        parent={parent}
        childNodes={children}
        siblings={siblings}
        onSelect={onSelectNode}
        onModeChange={onModeChange}
      />

      <div className="flex items-start gap-4">
        {navigationMode === "overview" && (
          <ContextOverviewRail
            graph={contextGraph}
            selectedNodeId={selectedNodeId}
            onSelect={onSelectNode}
          />
        )}

        <div className="min-w-0 flex-1">
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
        </div>
      </div>
    </main>
  );
}
