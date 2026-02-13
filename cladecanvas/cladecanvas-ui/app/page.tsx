
"use client";

import React, { useState, useEffect } from "react";
import DOMPurify from "dompurify";
import dynamic from "next/dynamic";

export type Node = {
  node_id: string;
  ott_id?: number;
  name: string;
  parent_node_id?: string;
  child_count?: number;
  has_metadata?: boolean;
};

export type Metadata = {
  node_id: string;
  ott_id?: number;
  common_name?: string;
  description?: string;
  full_description?: string;
  image_url?: string;
  wiki_page_url?: string;
  rank?: string;
};

const CladeTree = dynamic(() => import("@components/CladeTree"), { ssr: false });

export default function Page() {
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<Metadata[]>([]);
  const [selectedNode, setSelectedNode] = useState<Metadata | null>(null);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [treeRootNodeId, setTreeRootNodeId] = useState<string>("ott691846"); // Metazoa
  const [breadcrumb, setBreadcrumb] = useState<Node[]>([]);
  const API = process.env.NEXT_PUBLIC_API_BASE;

  const fetchNode = (nodeId: string) => {
    if (!nodeId) return;
    fetch(`${API}/node/metadata/${nodeId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Metadata not found");
        return res.json();
      })
      .then(setSelectedNode)
      .catch(() => setSelectedNode(null));
  };

  const buildBreadcrumbTrail = async (startingNodeId: string) => {
    try {
      const res = await fetch(`${API}/tree/lineage/${startingNodeId}`);
      if (!res.ok) return;
      const { lineage } = await res.json();
      setBreadcrumb(lineage);

      if (lineage.length > 1) {
        const parent = lineage[lineage.length - 2];
        setTreeRootNodeId(parent.node_id);
      }
    } catch {
      // silently fail for now
    }
  };

  const doSearch = () => {
    fetch(`${API}/search?q=${search}`)
      .then((res) => res.json())
      .then(setSearchResults);
  };

  return (
    <div className="bg-paper text-ink min-h-screen grid grid-cols-[auto,1fr] p-4 font-sans gap-6">
      <div className="col-span-2 flex justify-between items-center mb-4">
        <h1 className="title-heading">CladeCanvas</h1>
        <div className="flex gap-2 w-1/2">
          <input className="search-bar flex-1"
            placeholder="Search clades or species..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button
            className="bg-blue-600 text-white px-4 py-1 rounded"
            onClick={doSearch}
          >
            Search
          </button>
        </div>
      </div>

      <CladeTree
        api={API!}
        onSelect={(node) => {
          setActiveNodeId(node.node_id);
          fetchNode(node.node_id);
          buildBreadcrumbTrail(node.node_id);
        }}
        activeNodeId={activeNodeId}
        rootNodeId={treeRootNodeId}
      />

      <div className="flex flex-col gap-4">
        {searchResults.length > 0 && (
          <div className="bg-white shadow rounded p-3 max-h-40 overflow-y-auto border text-sm">
            {searchResults.map((res) => (
              <div
                key={res.node_id}
                className="cursor-pointer hover:bg-hovergray p-1"
                onClick={() => {
                  setSelectedNode(res);
                  setActiveNodeId(res.node_id);
                  setSearchResults([]);
                  buildBreadcrumbTrail(res.node_id);
                }}
              >
              <div className="cursor-pointer hover:bg-hovergray p-1">
                <span className={res.common_name ? "" : "font-mono text-xs text-[#888]"}>
                  {res.common_name || `OTT ${res.ott_id ?? res.node_id}`}
                </span>
              </div>
              </div>
            ))}
          </div>
        )}

        {breadcrumb.length > 1 && (
          <div className="text-sm text-[#777]">
            {breadcrumb.map((node, idx) => (
              <span key={node.node_id}>
                {idx > 0 && " › "}
                <span
                  className="cursor-pointer hover:underline"
                  onClick={() => {
                    setActiveNodeId(node.node_id);
                    fetchNode(node.node_id);
                    buildBreadcrumbTrail(node.node_id);
                  }}
                >
                  {node.name}
                </span>
              </span>
            ))}
          </div>
        )}

        {selectedNode ? (
          <div className="bg-white/70 shadow rounded-lg p-6 border border-[#e1dfda] prose max-w-none">
            <h2 className="text-2xl font-bold mb-2">
              {selectedNode.common_name || `OTT ${selectedNode.ott_id ?? selectedNode.node_id}`}
            </h2>
            {selectedNode.image_url && (
              <img src={selectedNode.image_url} alt={selectedNode.common_name} className="float-right max-h-64 ml-6 mt-1 mb-2 min-w-[220px] max-w-[360px] object-contain rounded border"
              />
            )}
            <p className="text-sm text-[#777] mb-1">{selectedNode.rank}</p>
            <p className="mb-4 text-gray-800">{selectedNode.description}</p>
            {selectedNode.full_description ? (
              <div
                className="prose text-gray-800 max-w-none"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(selectedNode.full_description),
                }}
              />
            ) : (
              <p className="italic text-sm text-[#777]">
                No Wikipedia description available for this clade.
              </p>
            )}
            {selectedNode.wiki_page_url && (
              <a href={selectedNode.wiki_page_url} target="_blank" rel="noopener noreferrer" className="link-highlight block mt-4"
              >
                View on Wikipedia
              </a>
            )}
          </div>
        ) : (
          <div className="text-gray-500">Select a node to see details</div>
        )}
      </div>
    </div>
  );
}
