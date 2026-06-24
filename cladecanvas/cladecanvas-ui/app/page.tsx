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
import { markEnd, markStart } from "./lib/performance";
import ContextOverviewRail from "./components/ContextOverviewRail";
import JumpControls from "./components/JumpControls";

const DEFAULT_ROOT = "ott691846"; // Metazoa

export default function Page() {
  return (
    <Suspense fallback={<LoadingShell />}>
      <ExplorerPage />
    </Suspense>
  );
}

function LoadingShell() {
  return (
    <main
      className="max-w-6xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8 min-h-screen"
      style={{ color: "var(--color-ink)" }}
    >
      <div className="skeleton h-8 w-44 mb-5" />
      <div className="skeleton h-[300px] w-full rounded-xl" />
      <div className="skeleton h-8 w-56 mt-6" />
      <div className="skeleton h-4 w-full mt-3" />
      <div className="skeleton h-4 w-3/4 mt-2" />
    </main>
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
  const [loadError, setLoadError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  const loadNode = useCallback(async (nodeId: string) => {
    const transitionMark = markStart("node_navigation", nodeId);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const isActive = () => requestIdRef.current === requestId && !controller.signal.aborted;

    setIsLoading(true);
    setLoadError(null);
    setSelectedNodeId(nodeId);
    setContextGraph(null);

    try {
      const node = await fetchNode(nodeId, controller.signal);
      if (!isActive()) return;

      const [meta, lin, kids] = await Promise.all([
        fetchMetadata(nodeId, controller.signal).catch(() => null),
        fetchLineage(nodeId, controller.signal).catch(() => [] as TreeNode[]),
        fetchChildren(nodeId, controller.signal).catch(() => [] as TreeNode[]),
      ]);
      if (!isActive()) return;

      setSelectedNode(node);
      setMetadata(meta);
      setLineage(lin);
      setChildren(topByScore(kids, 100));

      fetchContextGraph(nodeId, controller.signal)
        .then((graph) => {
          if (isActive()) setContextGraph(graph);
        })
        .catch((err: unknown) => {
          if (!isActive()) return;
          if (err instanceof DOMException && err.name === "AbortError") return;
          setContextGraph(null);
        });

      const parentNode = lin.length >= 2 ? lin[lin.length - 2] : null;
      setParent(parentNode);

      if (parentNode) {
        const parentKids = await fetchChildren(parentNode.node_id, controller.signal).catch(
          () => [] as TreeNode[]
        );
        if (!isActive()) return;
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
      if (!isActive()) return;
      setSelectedNode(null);
      setMetadata(null);
      setLineage([]);
      setParent(null);
      setSiblings([]);
      setChildren([]);
      setContextGraph(null);
      setLoadError(`Could not load ${nodeId}.`);
    } finally {
      markEnd(transitionMark, "node_navigation", nodeId, {
        aborted: String(controller.signal.aborted),
      });
      if (isActive()) setIsLoading(false);
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
      className="max-w-6xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8 min-h-screen"
      style={{ color: "var(--color-ink)" }}
    >
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4 mb-3 sm:mb-4">
        <h1
          className="text-2xl sm:text-3xl font-bold tracking-tight"
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


      {isLoading && selectedNode && (
        <div className="text-xs" style={{ color: "var(--color-ink-muted)" }}>
          Loading selection...
        </div>
      )}

      {loadError && (
        <div
          role="alert"
          className="my-4 rounded-lg p-4 text-sm"
          style={{
            background: "rgba(135, 64, 46, 0.1)",
            border: "1px solid rgba(135, 64, 46, 0.24)",
            color: "#87402e",
          }}
        >
          {loadError} Try another nearby clade or reload once the API is available.
        </div>
      )}

      <div className="explorer-layout">
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
