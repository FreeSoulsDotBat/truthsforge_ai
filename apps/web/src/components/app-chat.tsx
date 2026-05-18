import {
  Activity,
  Bot,
  BrainCircuit,
  Clipboard,
  LoaderCircle,
  MessageSquare,
  Paperclip,
  Search,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import type { ReactNode } from "react";

import { ModelingEditCard, ModelingPlanCard } from "../features/modeling-3d/components";
import { fileContentUrl, isImagePlatformFile, platformFileLabel } from "../features/files/file-domain";
import { type ChatMessageAttachment, messageMetadata } from "../features/chat/chat-domain";
import { imageUrlsFromMarkdown, renderMarkdown, stripImageMarkdown } from "../lib/message-content";
import type { StreamStatusEvent } from "../lib/api";
import type { ChatMessage } from "../types/api";
import type { PlatformFile } from "../types/api";

function OfficialReasoningSummary({ isActive, summary }: { isActive: boolean; summary?: string }) {
  if (!summary && !isActive) return null;

  return (
    <details
      className="mb-3 rounded-md border border-forge-amber/30 bg-[#18150f] p-2 text-xs"
      open={isActive || !!summary}
    >
      <summary className="cursor-pointer font-medium text-forge-amber">Resumo oficial do raciocínio</summary>
      {summary ? (
        <div className="mt-2 leading-5 text-forge-text">{renderMarkdown(summary)}</div>
      ) : (
        <p className="mt-2 text-forge-muted">Aguardando resumo autorizado do provedor.</p>
      )}
    </details>
  );
}

function runtimeStatusIcon(stage: string): ReactNode {
  if (stage === "deep_research") return <Search size={13} />;
  if (stage === "reasoning") return <BrainCircuit size={13} />;
  if (stage === "reasoning_summary") return <BrainCircuit size={13} />;
  if (stage === "answering" || stage === "done") return <Sparkles size={13} />;
  if (stage === "error" || stage === "blocked") return <ShieldCheck size={13} />;
  return <Activity size={13} />;
}

function ReasoningTrack({ statuses, isActive }: { statuses: StreamStatusEvent[]; isActive: boolean }) {
  if (!statuses.length) return null;

  const visibleStatuses = statuses.slice(-5);

  return (
    <div className="mb-3 rounded-md border border-forge-line bg-[#0c0d0f] p-2">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium text-forge-muted">
        {isActive ? <LoaderCircle size={13} className="animate-spin text-forge-amber" /> : <BrainCircuit size={13} />}
        <span>Trilha de raciocínio</span>
      </div>
      <div className="flex flex-col gap-1">
        {visibleStatuses.map((status, index) => {
          const isLast = index === visibleStatuses.length - 1;
          return (
            <div
              key={`${status.stage}:${index}`}
              className={[
                "flex items-start gap-2 rounded px-2 py-1 text-xs",
                isLast ? "bg-[#171716] text-forge-text" : "text-forge-muted"
              ].join(" ")}
            >
              <span className={isLast ? "mt-0.5 text-forge-amber" : "mt-0.5 text-forge-muted"}>
                {runtimeStatusIcon(status.stage)}
              </span>
              <span className="min-w-0">
                <span className="block font-medium">{status.label}</span>
                {status.detail && <span className="block text-forge-muted">{status.detail}</span>}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

type ResolvedAttachment = {
  id: string;
  label: string;
  contentType: string | null;
  url?: string;
  isImage: boolean;
};

function isImageAttachment(raw: { contentType: string | null; label: string }): boolean {
  if (raw.contentType?.startsWith("image/")) return true;
  return raw.label.toLowerCase().match(/\.(apng|avif|gif|jpe?g|png|svg|webp)$/) ? true : false;
}

function resolveAttachmentFromMetadata(
  attachment: ChatMessageAttachment,
  platformFilesById: Record<string, PlatformFile>
): ResolvedAttachment | null {
  const fileId = attachment.file_id ?? attachment.id ?? "";
  const platformFile = fileId ? platformFilesById[fileId] : undefined;
  const label =
    attachment.original_filename ?? attachment.filename ?? (platformFile ? platformFileLabel(platformFile) : "");
  if (!label) return null;
  const contentType = attachment.content_type ?? platformFile?.content_type ?? null;
  const url = attachment.url ?? (fileId ? fileContentUrl(fileId) : undefined);
  return {
    id: fileId || `${label}:${url ?? "local"}`,
    label,
    contentType,
    url,
    isImage: isImageAttachment({ contentType, label })
  };
}

function resolveAttachments(
  metadata: ReturnType<typeof messageMetadata>,
  platformFilesById: Record<string, PlatformFile>
): ResolvedAttachment[] {
  const resolved: ResolvedAttachment[] = [];
  const seen = new Set<string>();

  const addAttachment = (attachment: ResolvedAttachment | null) => {
    if (!attachment) return;
    const key = attachment.url ? `${attachment.id}:${attachment.url}` : attachment.id;
    if (seen.has(key)) return;
    seen.add(key);
    resolved.push(attachment);
  };

  if (Array.isArray(metadata.attached_files)) {
    for (const attachment of metadata.attached_files) {
      addAttachment(resolveAttachmentFromMetadata(attachment, platformFilesById));
    }
  }

  if (Array.isArray(metadata.attached_file_ids)) {
    for (const fileId of metadata.attached_file_ids) {
      const platformFile = platformFilesById[fileId];
      if (!platformFile) continue;
      addAttachment({
        id: platformFile.id,
        label: platformFileLabel(platformFile),
        contentType: platformFile.content_type ?? null,
        url: fileContentUrl(platformFile.id),
        isImage: isImagePlatformFile(platformFile)
      });
    }
  }

  return resolved;
}

/** Actions passed down from the chat host to make the in-chat plan card
 *  interactive (Onda 4 — ADR-013). All callbacks receive the plan id so
 *  the host can route to ``modeling3dApi.approvePlan`` / ``rejectPlan``
 *  via ``useModelingPlanActions``. When omitted, the card renders as
 *  read-only and the buttons disappear — useful for historical
 *  messages where the plan has already terminated. */
export interface ModelingPlanCardActions {
  onApprove?: (planId: string) => Promise<void> | void;
  onReject?: (planId: string, reason: string) => Promise<void> | void;
  onRetry?: (planId: string) => Promise<void> | void;
  onRevise?: (planId: string) => Promise<void> | void;
  isBusy?: boolean;
}

export function MessageBubble({
  message,
  platformFilesById,
  modelingPlanActions
}: {
  message: ChatMessage;
  platformFilesById: Record<string, PlatformFile>;
  modelingPlanActions?: ModelingPlanCardActions;
}) {
  const isUser = message.role === "user";
  const markdownImageUrls = imageUrlsFromMarkdown(message.content);
  const markdownText = stripImageMarkdown(message.content);
  const metadata = messageMetadata(message);
  const attachmentPreviews = resolveAttachments(metadata, platformFilesById);
  const attachmentImageUrls = attachmentPreviews.filter((attachment) => attachment.isImage && !!attachment.url);
  const attachmentFiles = attachmentPreviews.filter((attachment) => !attachment.isImage);
  const imageUrls = [...new Set([...markdownImageUrls, ...attachmentImageUrls.map((attachment) => attachment.url!)])];
  const statuses = metadata.runtime_statuses ?? (metadata.runtime_status ? [metadata.runtime_status] : []);
  const latestStatus = statuses[statuses.length - 1];
  const activeStage = latestStatus?.stage ?? "";
  const isActive = !isUser && !!statuses.length && !["done", "error", "blocked"].includes(activeStage);
  const reasoningSummary = metadata.reasoning_summary;
  const reasoningSummaryEnabled = !!metadata.reasoning_summary_enabled;
  const showRuntimePlaceholder =
    !isUser &&
    statuses.length > 0 &&
    !markdownText &&
    !metadata.modeling_plan &&
    imageUrls.length === 0 &&
    attachmentFiles.length === 0;

  return (
    <div
      className={[
        "max-w-[92%] rounded-md border px-4 py-3 text-sm leading-6 shadow-soft",
        isUser ? "ml-auto border-[#315473] bg-[#153047]" : "mr-auto border-forge-line bg-[#141615]"
      ].join(" ")}
    >
      <div className="mb-1 flex items-center justify-between gap-3 text-xs text-forge-muted">
        <span className="flex items-center gap-2">
          {isUser ? <MessageSquare size={14} /> : <Bot size={14} />}
          {isUser ? "Você" : "JUDITE"}
        </span>
        <button
          className="rounded p-1 text-forge-muted transition hover:bg-[#222a2f] hover:text-forge-text"
          onClick={() => void navigator.clipboard?.writeText(message.content)}
          aria-label="Copiar mensagem"
          title="Copiar mensagem"
        >
          <Clipboard size={13} />
        </button>
      </div>
      {showRuntimePlaceholder ? (
        <>
          <ReasoningTrack statuses={statuses} isActive={isActive} />
          <OfficialReasoningSummary isActive={reasoningSummaryEnabled && isActive} summary={reasoningSummary} />
          <div className="flex items-center gap-2 text-forge-muted">
            <LoaderCircle size={16} className="animate-spin text-forge-amber" />
            <span>{latestStatus?.label ?? "Pensando"}</span>
          </div>
        </>
      ) : (
        <>
          {!isUser && statuses.length > 0 && <ReasoningTrack statuses={statuses} isActive={isActive} />}
          {!isUser && (
            <OfficialReasoningSummary isActive={reasoningSummaryEnabled && isActive} summary={reasoningSummary} />
          )}
          {markdownText ? <div className="leading-6">{renderMarkdown(markdownText)}</div> : null}
          {!isUser && metadata.modeling_plan ? (
            metadata.modeling_plan.kind === "edit" &&
            metadata.modeling_plan.status !== "waiting_approval" ? (
              <ModelingEditCard plan={metadata.modeling_plan} />
            ) : (
              <ModelingPlanCard
                plan={metadata.modeling_plan}
                isBusy={modelingPlanActions?.isBusy}
                onApprove={
                  modelingPlanActions?.onApprove
                    ? () =>
                        modelingPlanActions.onApprove?.(
                          metadata.modeling_plan!.id
                        )
                    : undefined
                }
                onReject={
                  modelingPlanActions?.onReject
                    ? (reason: string) =>
                        modelingPlanActions.onReject?.(
                          metadata.modeling_plan!.id,
                          reason
                        )
                    : undefined
                }
                onRetry={
                  modelingPlanActions?.onRetry
                    ? () =>
                        modelingPlanActions.onRetry?.(
                          metadata.modeling_plan!.id
                        )
                    : undefined
                }
                onRevise={
                  modelingPlanActions?.onRevise
                    ? () =>
                        modelingPlanActions.onRevise?.(
                          metadata.modeling_plan!.id
                        )
                    : undefined
                }
              />
            )
          ) : null}
          {imageUrls.length > 0 ? (
            <div className={[markdownText ? "mt-3" : "", "grid gap-2"].join(" ").trim()}>
              {imageUrls.map((url) => (
                <img
                  key={url}
                  src={url}
                  alt="Prévia de imagem"
                  className="max-h-[520px] w-full rounded-md object-contain"
                />
              ))}
            </div>
          ) : null}
          {attachmentFiles.length > 0 ? (
            <div className={[markdownText || imageUrls.length ? "mt-3" : "", "flex flex-wrap gap-2"].join(" ").trim()}>
              {attachmentFiles.map((attachment) => (
                <a
                  key={attachment.id}
                  href={attachment.url ?? "#"}
                  target={attachment.url ? "_blank" : undefined}
                  rel={attachment.url ? "noreferrer" : undefined}
                  className={[
                    "inline-flex h-7 items-center gap-1 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs",
                    attachment.url ? "text-forge-amber hover:bg-[#171716]" : "cursor-default text-forge-muted"
                  ].join(" ")}
                  onClick={(event) => {
                    if (!attachment.url) event.preventDefault();
                  }}
                >
                  <Paperclip size={12} />
                  <span className="max-w-44 truncate">{attachment.label}</span>
                </a>
              ))}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
