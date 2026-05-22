import { useState } from "react";

import type { DocumentSearchResult } from "../../types/api";

/**
 * Owns the "indexar texto" / document-search form state of the knowledge view.
 * Extracted from App.tsx (architecture-map "monólitos de borda") to collapse six
 * `useState` calls into a single hook, which keeps App small enough for the React
 * Compiler to analyse. The index/search actions stay in App (they touch the
 * documents and knowledge-base lists) and consume these values + setters.
 */
export function useDocumentDraft() {
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentContent, setDocumentContent] = useState("");
  const [documentTags, setDocumentTags] = useState("");
  const [documentPinned, setDocumentPinned] = useState(false);
  const [documentQuery, setDocumentQuery] = useState("");
  const [documentResults, setDocumentResults] = useState<DocumentSearchResult[]>([]);

  function resetDraft() {
    setDocumentTitle("");
    setDocumentContent("");
    setDocumentTags("");
    setDocumentPinned(false);
  }

  return {
    documentTitle,
    setDocumentTitle,
    documentContent,
    setDocumentContent,
    documentTags,
    setDocumentTags,
    documentPinned,
    setDocumentPinned,
    documentQuery,
    setDocumentQuery,
    documentResults,
    setDocumentResults,
    resetDraft
  };
}
