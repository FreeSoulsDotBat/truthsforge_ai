import { X } from "lucide-react";

import type { DocumentRecord, PlatformFile } from "../../../types/api";
import { platformFileLabel } from "../../files/file-domain";

export interface ComposerAttachmentsProps {
  attachedFiles: File[];
  attachedPlatformFileIds: string[];
  attachedDocumentIds: string[];
  platformFiles: PlatformFile[];
  documents: DocumentRecord[];
  onRemoveFile: (index: number) => void;
  onRemovePlatformFile: (fileId: string) => void;
  onRemoveDocument: (documentId: string) => void;
}

/**
 * Pending-attachment chips shown above the chat input (local uploads, platform
 * files and indexed documents). Extracted from App.tsx (architecture-map
 * "monólitos de borda"); presentational.
 */
export function ComposerAttachments({
  attachedFiles,
  attachedPlatformFileIds,
  attachedDocumentIds,
  platformFiles,
  documents,
  onRemoveFile,
  onRemovePlatformFile,
  onRemoveDocument
}: ComposerAttachmentsProps) {
  if (!attachedFiles.length && !attachedPlatformFileIds.length && !attachedDocumentIds.length) {
    return null;
  }
  return (
    <div className="mb-2 flex flex-wrap gap-2 text-xs text-forge-muted">
      {attachedFiles.map((file, index) => (
        <button
          key={`${file.name}:${file.size}:${index}`}
          type="button"
          className="inline-flex h-7 items-center gap-1 rounded-md border border-forge-line-soft bg-forge-ink-deep px-2 text-xs text-forge-muted transition hover:text-forge-text"
          onClick={() => onRemoveFile(index)}
          title={`Remover ${file.name}`}
        >
          <span className="max-w-40 truncate">{file.name}</span>
          <X size={12} />
        </button>
      ))}
      {attachedPlatformFileIds.map((fileId) => {
        const platformFile = platformFiles.find((item) => item.id === fileId);
        return (
          <button
            key={fileId}
            type="button"
            className="inline-flex h-7 items-center gap-1 rounded-md border border-forge-line-soft bg-forge-ink-deep px-2 text-xs text-forge-muted transition hover:text-forge-text"
            onClick={() => onRemovePlatformFile(fileId)}
            title={`Remover ${platformFile ? platformFileLabel(platformFile) : "arquivo"}`}
          >
            <span className="max-w-40 truncate">{platformFile ? platformFileLabel(platformFile) : "arquivo"}</span>
            <X size={12} />
          </button>
        );
      })}
      {attachedDocumentIds.map((documentId) => (
        <button
          key={documentId}
          type="button"
          className="inline-flex h-7 items-center gap-1 rounded-md border border-forge-line-soft bg-forge-ink-deep px-2 text-xs text-forge-muted transition hover:text-forge-text"
          onClick={() => onRemoveDocument(documentId)}
          title={`Remover ${documents.find((document) => document.id === documentId)?.title ?? "contexto"}`}
        >
          <span className="max-w-40 truncate">
            {documents.find((document) => document.id === documentId)?.title ?? "contexto"}
          </span>
          <X size={12} />
        </button>
      ))}
    </div>
  );
}
