import type { TreeNode } from "./api";

const RANK_PRIORITY: Record<string, number> = {
  kingdom: 1000,
  phylum: 800,
  clade: 900,
  class: 600,
  order: 500,
  family: 400,
  genus: 300,
  species: 200,
};

export function isSynthetic(node: TreeNode): boolean {
  return node.node_id.startsWith("mrcaott");
}

export function score(node: TreeNode): number {
  const metadataScore = node.has_metadata ? 100 : 0;
  const childScore = typeof node.child_count === "number" ? node.child_count : 0;
  const rankBoost = node.rank ? (RANK_PRIORITY[node.rank.toLowerCase()] ?? 0) : 0;
  const tipsBoost = node.num_tips ? Math.log10(node.num_tips) * 100 : 0;
  return metadataScore + childScore + rankBoost + tipsBoost;
}

/** Filter out junk nodes (environmental samples, missing tip counts) */
export function filterClean(nodes: TreeNode[]): TreeNode[] {
  const cleaned = nodes.filter(
    (n) =>
      typeof n.name === "string" &&
      !n.name.toLowerCase().includes("environmental") &&
      n.num_tips != null
  );
  return cleaned.length > 0 ? cleaned : nodes;
}

/** Deduplicate by node_id */
function dedup(nodes: TreeNode[]): TreeNode[] {
  const seen = new Set<string>();
  return nodes.filter((n) => {
    if (seen.has(n.node_id)) return false;
    seen.add(n.node_id);
    return true;
  });
}

/** Sort by score descending, truncate to limit */
export function topByScore(nodes: TreeNode[], limit: number): TreeNode[] {
  return dedup(filterClean(nodes))
    .sort((a, b) => score(b) - score(a))
    .slice(0, limit);
}
