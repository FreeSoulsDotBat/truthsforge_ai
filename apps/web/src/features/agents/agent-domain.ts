import type { Agent, AgentLLMConfig, AgentUpsert, ModelConfig } from "../../types/api";
import { optionalNumber } from "../../shared/utils/common";

export const defaultLLMConfig: AgentLLMConfig = {
  provider: "openai",
  provider_model_id: null,
  display_name: null,
  input_token_cost_per_million: null,
  output_token_cost_per_million: null,
  temperature: 1,
  top_p: 1,
  top_k: null,
  max_output_tokens: 2048,
  reasoning_effort: null,
  reasoning_budget_tokens: null,
  verbosity: null,
  response_format: "text",
  tool_choice: "auto",
  parallel_tool_calls: true,
  presence_penalty: null,
  frequency_penalty: null,
  seed: null,
  stop_sequences: []
};

export function createEmptyAgentDraft(): AgentUpsert {
  return {
    name: "",
    description: "",
    system_prompt: "",
    model_id: null,
    llm_config: { ...defaultLLMConfig, stop_sequences: [] },
    enabled: true,
    role: "specialist",
    collaboration_mode: "delegate",
    handoff_triggers: [],
    tags: [],
    tools_allowed: [],
    allowed_project_ids: ["project_general"],
    knowledge_base_ids: []
  };
}

export function agentRequiredFieldsComplete(agent: AgentUpsert): boolean {
  return Boolean(
    agent.name.trim() &&
    agent.system_prompt.trim() &&
    agent.role &&
    agent.collaboration_mode &&
    agent.llm_config.provider &&
    agent.llm_config.provider_model_id?.trim()
  );
}

export function llmConfigFromAgent(agent?: Agent | null, models: ModelConfig[] = []): AgentLLMConfig {
  const baseModel = models.find((model) => model.id === agent?.model_id);
  const baseConfig: Partial<AgentLLMConfig> = baseModel
    ? {
        provider: baseModel.provider,
        provider_model_id: baseModel.provider_model_id,
        display_name: baseModel.display_name,
        input_token_cost_per_million: baseModel.input_token_cost_per_million,
        output_token_cost_per_million: baseModel.output_token_cost_per_million,
        temperature: baseModel.temperature,
        top_p: baseModel.top_p,
        top_k: baseModel.top_k,
        max_output_tokens: baseModel.max_output_tokens,
        reasoning_effort: baseModel.reasoning_effort,
        reasoning_budget_tokens: baseModel.reasoning_budget_tokens,
        verbosity: baseModel.verbosity,
        response_format: baseModel.response_format,
        tool_choice: baseModel.tool_choice,
        parallel_tool_calls: baseModel.parallel_tool_calls,
        presence_penalty: baseModel.presence_penalty,
        frequency_penalty: baseModel.frequency_penalty,
        seed: baseModel.seed,
        stop_sequences: baseModel.stop_sequences
      }
    : {};
  return {
    ...defaultLLMConfig,
    ...baseConfig,
    ...(agent?.llm_config ?? {}),
    stop_sequences: agent?.llm_config?.stop_sequences ?? baseModel?.stop_sequences ?? []
  };
}

export function normalizeLLMConfig(config: AgentLLMConfig): AgentLLMConfig {
  return {
    ...defaultLLMConfig,
    ...config,
    provider_model_id: config.provider_model_id?.trim() || null,
    display_name: config.display_name?.trim() || null,
    input_token_cost_per_million: optionalNumber(config.input_token_cost_per_million),
    output_token_cost_per_million: optionalNumber(config.output_token_cost_per_million),
    temperature: optionalNumber(config.temperature),
    top_p: optionalNumber(config.top_p),
    top_k: optionalNumber(config.top_k),
    max_output_tokens: optionalNumber(config.max_output_tokens),
    reasoning_budget_tokens: optionalNumber(config.reasoning_budget_tokens),
    presence_penalty: optionalNumber(config.presence_penalty),
    frequency_penalty: optionalNumber(config.frequency_penalty),
    seed: optionalNumber(config.seed),
    stop_sequences: config.stop_sequences.map((item) => item.trim()).filter(Boolean)
  };
}
