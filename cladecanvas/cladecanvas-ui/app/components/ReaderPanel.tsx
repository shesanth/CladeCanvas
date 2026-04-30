"use client";

import type { ReactNode } from "react";
import DOMPurify from "dompurify";
import { motion, AnimatePresence } from "framer-motion";
import type { TreeNode, Metadata, FieldSource } from "../lib/api";
import { isSynthetic } from "../lib/scoring";

type Props = {
  metadata: Metadata | null;
  node: TreeNode | null;
  children?: ReactNode;
};

const STALE_AFTER_DAYS = 365;
const AGING_AFTER_DAYS = 90;

function parseDate(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value?: string | null) {
  const date = parseDate(value);
  if (!date) return null;
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function stalenessFor(value?: string | null) {
  const date = parseDate(value);
  if (!date) return { label: "Unknown freshness", tone: "muted" as const };
  const ageMs = Date.now() - date.getTime();
  const days = Math.max(0, Math.floor(ageMs / 86400000));
  if (days > STALE_AFTER_DAYS) return { label: "Stale", tone: "warn" as const };
  if (days > AGING_AFTER_DAYS) return { label: "Aging", tone: "soft" as const };
  return { label: "Fresh", tone: "good" as const };
}

function confidenceLabel(value?: number | null) {
  if (typeof value !== "number") return "Unknown confidence";
  if (value >= 0.85) return "High confidence";
  if (value >= 0.55) return "Medium confidence";
  return "Low confidence";
}

function provenanceText(field?: FieldSource | null) {
  if (!field?.source_label) return null;
  return `${field.fallback ? "Fallback from" : "From"} ${field.source_label}`;
}

function Chip({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "muted" | "good" | "soft" | "warn";
}) {
  const palette = {
    muted: { background: "rgba(122, 110, 93, 0.12)", color: "var(--color-ink-muted)" },
    good: { background: "rgba(60, 110, 113, 0.14)", color: "var(--color-accent)" },
    soft: { background: "rgba(139, 105, 20, 0.14)", color: "var(--clade-branch-active)" },
    warn: { background: "rgba(135, 64, 46, 0.14)", color: "#87402e" },
  }[tone];

  return (
    <span
      className="text-xs px-2.5 py-1 rounded-full font-medium"
      style={palette}
    >
      {children}
    </span>
  );
}

function FieldSourceLabel({ source }: { source?: FieldSource | null }) {
  const text = provenanceText(source);
  if (!text) return null;
  const className = "text-xs underline-offset-2";
  if (!source?.source_url) {
    return (
      <span className="text-xs" style={{ color: "var(--color-ink-muted)" }}>
        {text}
      </span>
    );
  }
  return (
    <a
      href={source.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className={`${className} underline`}
      style={{ color: "var(--color-ink-muted)" }}
    >
      {text}
    </a>
  );
}

export default function ReaderPanel({ metadata, node, children }: Props) {
  if (!node) {
    return (
      <div
        className="text-center py-16 text-sm"
        style={{ color: "var(--color-ink-muted)" }}
      >
        Select a node to begin reading
      </div>
    );
  }

  const key = node.node_id;
  const showSyntheticFallback = !metadata && isSynthetic(node);
  const title =
    metadata?.common_name ||
    node.display_name ||
    node.name;
  const latinName = node.name !== title ? node.name : null;
  const fieldSources: Record<string, FieldSource> = metadata?.field_sources ?? {};
  const sourceLabel = metadata?.source_label ?? (metadata ? "Wikidata/Wikipedia" : null);
  const sourceUrl =
    metadata?.source_url ??
    (metadata?.wikidata_q ? `https://www.wikidata.org/wiki/${metadata.wikidata_q}` : null);
  const enrichedAt = metadata?.enriched_at ?? metadata?.last_updated ?? null;
  const enrichedAtLabel = formatDate(enrichedAt);
  const staleness = stalenessFor(enrichedAt);
  const confidence =
    metadata?.provenance_confidence ?? metadata?.enriched_score ?? null;

  return (
    <AnimatePresence mode="wait">
      <motion.article
        key={key}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -12 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="rounded-xl p-6 md:p-8"
        style={{
          background: "var(--color-paper-light)",
          border: "1px solid var(--color-border)",
        }}
      >
        {/* Header */}
        <div className="mb-4">
          <h2
            className="text-2xl md:text-3xl font-bold leading-tight"
            style={{
              fontFamily: "var(--font-playfair), serif",
              color: "var(--color-ink)",
            }}
          >
            {title}
          </h2>
          {latinName && (
            <p
              className="text-base mt-1"
              style={{
                fontFamily: "var(--font-playfair), serif",
                fontStyle: "italic",
                color: "var(--color-ink-muted)",
              }}
            >
              {latinName}
            </p>
          )}
          {metadata?.common_name && (
            <div className="mt-1">
              <FieldSourceLabel source={fieldSources.common_name} />
            </div>
          )}
          <div className="flex items-center gap-3 mt-2">
            {(metadata?.rank || node.rank) && (
              <span
                className="text-xs px-2.5 py-1 rounded-full font-medium capitalize"
                style={{
                  background: "var(--color-accent)",
                  color: "var(--color-paper-light)",
                }}
              >
                {metadata?.rank || node.rank}
              </span>
            )}
            {node.num_tips && (
              <span
                className="text-sm"
                style={{ color: "var(--color-ink-muted)" }}
              >
                {node.num_tips.toLocaleString()} species
              </span>
            )}
          </div>
          {metadata && (
            <div className="flex flex-wrap items-center gap-2 mt-3">
              {sourceLabel && sourceUrl ? (
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs px-2.5 py-1 rounded-full font-medium underline underline-offset-2"
                  style={{
                    background: "rgba(60, 110, 113, 0.1)",
                    color: "var(--color-accent)",
                  }}
                >
                  Source: {sourceLabel}
                </a>
              ) : sourceLabel ? (
                <Chip tone="good">Source: {sourceLabel}</Chip>
              ) : null}
              <Chip tone={confidence !== null && confidence >= 0.85 ? "good" : "soft"}>
                {confidenceLabel(confidence)}
              </Chip>
              <Chip tone={staleness.tone}>{staleness.label}</Chip>
              {enrichedAtLabel && (
                <span
                  className="text-xs"
                  style={{ color: "var(--color-ink-muted)" }}
                >
                  Last enriched {enrichedAtLabel}
                </span>
              )}
              {metadata.source_match_method === "taxon_name" && (
                <Chip tone="soft">Taxon-name fallback</Chip>
              )}
            </div>
          )}
        </div>

        {/* Image */}
        {metadata?.image_url && (
          <figure className="float-right ml-6 mb-4 max-w-[280px] md:max-w-[360px]">
            <motion.img
              src={metadata.image_url}
              alt={title}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.1, duration: 0.3 }}
              className="rounded-lg w-full object-contain"
              style={{
                border: "2px solid var(--color-border)",
                boxShadow: "0 4px 16px rgba(44, 36, 22, 0.1)",
              }}
            />
            <figcaption className="mt-1 text-right">
              <FieldSourceLabel source={fieldSources.image_url} />
            </figcaption>
          </figure>
        )}

        {/* Content */}
        {showSyntheticFallback ? (
          <div>
            <p
              className="text-sm mb-2"
              style={{ color: "var(--color-ink-muted)", fontStyle: "italic" }}
            >
              Branching point in the tree of life
            </p>
            {node.num_tips && (
              <p style={{ color: "var(--color-ink)" }}>
                This clade encompasses{" "}
                <strong>{node.num_tips.toLocaleString()}</strong> descendant
                species.
              </p>
            )}
          </div>
        ) : metadata ? (
          <div className="reader-prose">
            {metadata.description && (
              <div className="mb-4">
                <p className="text-base leading-relaxed mb-1" style={{ fontSize: "1.05rem" }}>
                  {metadata.description}
                </p>
                <FieldSourceLabel source={fieldSources.description} />
              </div>
            )}
            {metadata.full_description && (
              <div>
                <div
                  dangerouslySetInnerHTML={{
                    __html: DOMPurify.sanitize(metadata.full_description),
                  }}
                />
                <FieldSourceLabel source={fieldSources.full_description} />
              </div>
            )}
          </div>
        ) : (
          <p
            className="text-sm"
            style={{ color: "var(--color-ink-muted)", fontStyle: "italic" }}
          >
            No Wikipedia description available for this clade.
          </p>
        )}

        {/* Clear float */}
        <div className="clear-both" />

        {/* Children cards slot */}
        {children && <div className="mt-6">{children}</div>}

        {/* Wikipedia link */}
        {metadata?.wiki_page_url && (
          <a
            href={metadata.wiki_page_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 mt-6 text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150"
            style={{
              color: "var(--color-accent)",
              border: "1px solid var(--color-accent)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--color-accent)";
              e.currentTarget.style.color = "var(--color-paper-light)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--color-accent)";
            }}
          >
            View on Wikipedia ↗
          </a>
        )}
      </motion.article>
    </AnimatePresence>
  );
}
