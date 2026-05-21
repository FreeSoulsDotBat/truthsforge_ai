import type {
  ChatAttachmentAnalyzeResponse,
  ModelingCapabilities,
  ModelingModelVersion,
  ModelingPlan,
  ModelingPrintabilityReport,
  ModelingSoftware,
  ModelingToolCall
} from "../../types/api";

export type {
  ChatModeling3DContext,
  ChatSession,
  ModelingApprovalRequest,
  ModelingExecutionResult,
  ModelingPlan,
  ModelingPlanEdit,
  ModelingPlanEditStep,
  ModelingPlanKind,
  ModelingPlanStatus,
  ModelingPlanStep,
  ModelingPrintabilityReport,
  ModelingRiskLevel,
  ModelingSoftware,
  ModelingStepStatus,
  ModelingToolCall
} from "../../types/api";

export type Modeling3DSoftwarePreference = ModelingSoftware;

export type Modeling3DSettings = {
  enabled: boolean;
  software: Modeling3DSoftwarePreference;
};

export type Modeling3DChatPayload = {
  enabled: boolean;
  mode: "safe_auto";
  software_override: ModelingSoftware | null;
};

export type Modeling3DDiagnostics = {
  capabilities: ModelingCapabilities;
  plans: ModelingPlan[];
  toolCalls: ModelingToolCall[];
  printabilityReports: ModelingPrintabilityReport[];
  modelVersions: ModelingModelVersion[];
};

export type AttachmentAnalysisResult = ChatAttachmentAnalyzeResponse;
