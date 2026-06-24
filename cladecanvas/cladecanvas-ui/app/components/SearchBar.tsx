"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { searchNodes, type SearchResult } from "../lib/api";

type Props = {
  onSelect: (nodeId: string) => void;
};

export default function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const searchCounterRef = useRef(0);

  const doSearch = useCallback(async (q: string) => {
    const normalized = q.trim();
    if (normalized.length < 3) {
      setResults([]);
      setIsOpen(false);
      setIsSearching(false);
      return;
    }
    searchCounterRef.current += 1;
    const searchId = searchCounterRef.current;
    setIsSearching(true);
    try {
      const data = await searchNodes(normalized);
      if (searchId !== searchCounterRef.current) return;
      setResults(data);
      setIsOpen(data.length > 0);
      setActiveIndex(-1);
    } finally {
      if (searchId === searchCounterRef.current) setIsSearching(false);
    }
  }, []);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, doSearch]);

  // Click outside to close
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selectResult = (result: SearchResult) => {
    onSelect(result.node_id);
    setQuery("");
    setResults([]);
    setIsOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      selectResult(results[activeIndex]);
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const fieldBadge = (field: string | null | undefined) => {
    if (!field) return null;
    const labels: Record<string, string> = {
      common_name: "name",
      description: "desc",
      full_description: "article",
    };
    return (
      <span
        className="text-[10px] px-1.5 py-0.5 rounded-full uppercase tracking-wider"
        style={{
          background: "var(--color-border)",
          color: "var(--color-ink-muted)",
        }}
      >
        {labels[field] ?? field}
      </span>
    );
  };

  return (
    <div ref={containerRef} className="relative w-full sm:max-w-md">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => results.length > 0 && setIsOpen(true)}
        placeholder="Search clades or species…"
        className="w-full px-4 py-2.5 sm:py-2 rounded-lg text-base sm:text-sm"
        style={{
          background: "var(--color-paper-light)",
          border: "1px solid var(--color-border)",
          color: "var(--color-ink)",
          fontFamily: "var(--font-inter), sans-serif",
        }}
      />

      {isOpen && (
        <div
          className="absolute z-50 w-full mt-1 rounded-lg shadow-lg overflow-hidden max-h-[70vh] sm:max-h-80 overflow-y-auto"
          style={{
            background: "var(--color-paper-light)",
            border: "1px solid var(--color-border)",
          }}
        >
          {isSearching && (
            <div
              className="px-4 py-2 text-xs"
              style={{ color: "var(--color-ink-muted)" }}
            >
              Searching...
            </div>
          )}
          {results.map((result, idx) => (
            <div
              key={result.node_id}
              onClick={() => selectResult(result)}
              onMouseEnter={() => setActiveIndex(idx)}
              className="px-4 py-3 sm:py-2.5 cursor-pointer transition-colors duration-100"
              style={{
                background:
                  idx === activeIndex
                    ? "var(--color-paper)"
                    : "transparent",
              }}
            >
              <div className="flex min-w-0 items-center gap-2">
                <span
                  className="min-w-0 truncate font-medium text-sm"
                  style={{ color: "var(--color-ink)" }}
                >
                  {result.common_name || result.node_id}
                </span>
                {fieldBadge(result.match_field)}
              </div>
              {result.match_snippet && (
                <p
                  className="text-xs mt-0.5 line-clamp-1"
                  style={{ color: "var(--color-ink-muted)" }}
                >
                  {result.match_snippet}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
