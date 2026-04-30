export type TreeNode = {
  node_id: string;
  ott_id?: number | null;
  name: string;
  parent_node_id?: string | null;
  child_count?: number | null;
  has_metadata?: boolean | null;
  rank?: string | null;
  num_tips?: number | null;
  display_name?: string | null;
};

export type Metadata = {
  node_id: string;
  ott_id?: number | null;
  common_name?: string | null;
  description?: string | null;
  full_description?: string | null;
  image_url?: string | null;
  wiki_page_url?: string | null;
  rank?: string | null;
  enriched_score?: number | null;
};

export type SearchResult = {
  node_id: string;
  ott_id?: number | null;
  common_name?: string | null;
  description?: string | null;
  image_url?: string | null;
  wiki_page_url?: string | null;
  enriched_score?: number | null;
  match_field?: string | null;
  match_snippet?: string | null;
};

export type NavigationMode = "local" | "overview";

export type ContextGraphNode = TreeNode & {
  kind: "lineage" | "sibling" | "child";
  depth: number;
  is_focus: boolean;
};

export type ContextGraphEdge = {
  source: string;
  target: string;
  kind: "lineage" | "sibling" | "child";
};

export type ContextGraph = {
  focus_node_id: string;
  lineage: TreeNode[];
  nodes: ContextGraphNode[];
  edges: ContextGraphEdge[];
  omitted_by_parent: Record<string, number>;
};

const API = process.env.NEXT_PUBLIC_API_BASE ?? "";

// Session-level cache — cleared on page reload, which is fine
const nodeCache = new Map<string, TreeNode>();
const metadataCache = new Map<string, Metadata | null>();
const childrenCache = new Map<string, TreeNode[]>();
const lineageCache = new Map<string, TreeNode[]>();
const contextGraphCache = new Map<string, ContextGraph>();

async function fetchJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API}${path}`, { signal });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function fetchNode(nodeId: string): Promise<TreeNode> {
  const cached = nodeCache.get(nodeId);
  if (cached) return cached;
  const res = await fetch(`${API}/node/${nodeId}`);
  if (!res.ok) throw new Error(`${res.status}`);
  const node: TreeNode = await res.json();
  nodeCache.set(nodeId, node);
  return node;
}

export async function fetchMetadata(
  nodeId: string,
  signal?: AbortSignal
): Promise<Metadata | null> {
  if (metadataCache.has(nodeId)) return metadataCache.get(nodeId)!;
  try {
    const meta = await fetchJSON<Metadata>(`/node/metadata/${nodeId}`, signal);
    metadataCache.set(nodeId, meta);
    return meta;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    metadataCache.set(nodeId, null);
    return null;
  }
}

export async function fetchChildren(nodeId: string): Promise<TreeNode[]> {
  const cached = childrenCache.get(nodeId);
  if (cached) return cached;
  const children = await fetchJSON<TreeNode[]>(`/tree/children/${nodeId}`);
  childrenCache.set(nodeId, children);
  // Populate node cache too
  for (const child of children) nodeCache.set(child.node_id, child);
  return children;
}

export async function fetchLineage(nodeId: string): Promise<TreeNode[]> {
  const cached = lineageCache.get(nodeId);
  if (cached) return cached;
  const data = await fetchJSON<{ lineage: TreeNode[] }>(`/tree/lineage/${nodeId}`);
  const lineage = data.lineage;
  lineageCache.set(nodeId, lineage);
  for (const node of lineage) nodeCache.set(node.node_id, node);
  return lineage;
}

export async function fetchContextGraph(nodeId: string): Promise<ContextGraph> {
  const cached = contextGraphCache.get(nodeId);
  if (cached) return cached;
  const graph = await fetchJSON<ContextGraph>(`/tree/context/${nodeId}`);
  contextGraphCache.set(nodeId, graph);
  for (const node of graph.nodes) nodeCache.set(node.node_id, node);
  lineageCache.set(nodeId, graph.lineage);
  return graph;
}

export async function searchNodes(query: string): Promise<SearchResult[]> {
  if (!query.trim()) return [];
  return fetchJSON<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`);
}
