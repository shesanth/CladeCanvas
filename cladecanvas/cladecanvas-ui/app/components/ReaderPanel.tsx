"use client";

import type { ReactNode } from "react";
import DOMPurify from "dompurify";
import { motion, AnimatePresence } from "framer-motion";
import type { TreeNode, Metadata } from "../lib/api";
import { isSynthetic } from "../lib/scoring";

type Props = {
  metadata: Metadata | null;
  node: TreeNode | null;
  children?: ReactNode;
};

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
        </div>

        {/* Image */}
        {metadata?.image_url && (
          <motion.img
            src={metadata.image_url}
            alt={title}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.3 }}
            className="float-right ml-6 mb-4 rounded-lg max-w-[280px] md:max-w-[360px] object-contain"
            style={{
              border: "2px solid var(--color-border)",
              boxShadow: "0 4px 16px rgba(44, 36, 22, 0.1)",
            }}
          />
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
              <p className="text-base leading-relaxed mb-4" style={{ fontSize: "1.05rem" }}>
                {metadata.description}
              </p>
            )}
            {metadata.full_description && (
              <div
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(metadata.full_description),
                }}
              />
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
