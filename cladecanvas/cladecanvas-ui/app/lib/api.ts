import { markEnd, markStart, recordDuration } from "./performance";

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
  wikidata_q?: string | null;
  common_name?: string | null;
  description?: string | null;
  full_description?: string | null;
  image_url?: string | null;
  image_thumb?: string | null;
  wiki_page_url?: string | null;
  rank?: string | null;
  last_updated?: string | null;
  enriched_score?: number | null;
  source_label?: string | null;
  source_url?: string | null;
  source_match_method?: string | null;
  enriched_at?: string | null;
  provenance_confidence?: number | null;
  field_sources?: Record<string, FieldSource>;
};

export type FieldSource = {
  source_label?: string | null;
  source_url?: string | null;
  fallback?: boolean | null;
};

export type SearchResult = {
  node_id: string;
  ott_id?: number | null;
  common_name?: string | null;
  display_name?: string | null;
  description?: string | null;
  image_url?: string | null;
  wiki_page_url?: string | null;
  enriched_score?: number | null;
  source_label?: string | null;
  enriched_at?: string | null;
  provenance_confidence?: number | null;
  match_field?: string | null;
  match_snippet?: string | null;
  match_type?: string | null;
  score?: number | null;
  score_breakdown?: Record<string, unknown> | null;
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

const API = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8600").trim();
const CHILDREN_PAGE_LIMIT = 200;

// Session-level cache — cleared on page reload, which is fine
const nodeCache = new Map<string, TreeNode>();
const metadataCache = new Map<string, Metadata | null>();
const childrenCache = new Map<string, TreeNode[]>();
const lineageCache = new Map<string, TreeNode[]>();
const contextGraphCache = new Map<string, ContextGraph>();

async function fetchJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const started = typeof performance !== "undefined" ? performance.now() : 0;
  const res = await fetch(`${API}${path}`, { signal });
  if (started) {
    recordDuration("api_request", path, performance.now() - started, {
      status: String(res.status),
    });
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function fetchJSONWithHeaders<T>(
  path: string,
  signal?: AbortSignal
): Promise<{ data: T; headers: Headers }> {
  const started = typeof performance !== "undefined" ? performance.now() : 0;
  const res = await fetch(`${API}${path}`, { signal });
  if (started) {
    recordDuration("api_request", path, performance.now() - started, {
      status: String(res.status),
    });
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return { data: await res.json(), headers: res.headers };
}

export async function fetchNode(nodeId: string, signal?: AbortSignal): Promise<TreeNode> {
  const cached = nodeCache.get(nodeId);
  if (cached) {
    recordDuration("cache_lookup", "node", 0, { hit: "true" });
    return cached;
  }
  const mark = markStart("api_request", `/node/${nodeId}`);
  const res = await fetch(`${API}/node/${nodeId}`, { signal });
  markEnd(mark, "api_request", `/node/${nodeId}`, { status: String(res.status) });
  if (!res.ok) throw new Error(`${res.status}`);
  const node: TreeNode = await res.json();
  nodeCache.set(nodeId, node);
  recordDuration("cache_lookup", "node", 0, { hit: "false" });
  return node;
}

export async function fetchMetadata(
  nodeId: string,
  signal?: AbortSignal
): Promise<Metadata | null> {
  if (metadataCache.has(nodeId)) {
    recordDuration("cache_lookup", "metadata", 0, { hit: "true" });
    return metadataCache.get(nodeId)!;
  }
  try {
    const meta = await fetchJSON<Metadata>(`/node/metadata/${nodeId}`, signal);
    metadataCache.set(nodeId, meta);
    recordDuration("cache_lookup", "metadata", 0, { hit: "false" });
    return meta;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    metadataCache.set(nodeId, null);
    recordDuration("cache_lookup", "metadata", 0, { hit: "false" });
    return null;
  }
}

export async function fetchChildren(
  nodeId: string,
  signal?: AbortSignal
): Promise<TreeNode[]> {
  const cached = childrenCache.get(nodeId);
  if (cached) {
    recordDuration("cache_lookup", "children", 0, { hit: "true" });
    return cached;
  }
  const children: TreeNode[] = [];
  let offset = 0;
  let hasMore = true;

  while (hasMore) {
    const { data, headers } = await fetchJSONWithHeaders<TreeNode[]>(
      `/tree/children/${nodeId}?limit=${CHILDREN_PAGE_LIMIT}&offset=${offset}`,
      signal
    );
    children.push(...data);

    const limitHeader = Number(headers.get("X-Limit"));
    const pageLimit = Number.isFinite(limitHeader) && limitHeader > 0 ? limitHeader : data.length;
    hasMore = headers.get("X-Has-More") === "true";
    offset += pageLimit || data.length;

    if (data.length === 0) break;
  }

  childrenCache.set(nodeId, children);
  recordDuration("cache_lookup", "children", 0, { hit: "false" });
  // Populate node cache too
  for (const child of children) nodeCache.set(child.node_id, child);
  return children;
}

export async function fetchLineage(
  nodeId: string,
  signal?: AbortSignal
): Promise<TreeNode[]> {
  const cached = lineageCache.get(nodeId);
  if (cached) {
    recordDuration("cache_lookup", "lineage", 0, { hit: "true" });
    return cached;
  }
  const data = await fetchJSON<{ lineage: TreeNode[] }>(
    `/tree/lineage/${nodeId}`,
    signal
  );
  const lineage = data.lineage;
  lineageCache.set(nodeId, lineage);
  recordDuration("cache_lookup", "lineage", 0, { hit: "false" });
  for (const node of lineage) nodeCache.set(node.node_id, node);
  return lineage;
}

export async function fetchContextGraph(
  nodeId: string,
  signal?: AbortSignal
): Promise<ContextGraph> {
  const cached = contextGraphCache.get(nodeId);
  if (cached) return cached;
  const graph = await fetchJSON<ContextGraph>(`/tree/context/${nodeId}`, signal);
  contextGraphCache.set(nodeId, graph);
  for (const node of graph.nodes) nodeCache.set(node.node_id, node);
  lineageCache.set(nodeId, graph.lineage);
  return graph;
}

export async function searchNodes(query: string): Promise<SearchResult[]> {
  if (!query.trim()) return [];
  return fetchJSON<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`);
}
