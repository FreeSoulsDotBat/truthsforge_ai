import { useState } from "react";

import { modeling3dApi } from "../api";
import type { AttachmentAnalysisResult } from "../types";

export function useAttachmentAnalysis(chatId: string | null) {
  const [analysis, setAnalysis] = useState<AttachmentAnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyze(fileId: string) {
    if (!chatId) {
      setError("Chat 3D ainda não foi criado.");
      return null;
    }
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await modeling3dApi.analyzeAttachment(chatId, fileId);
      setAnalysis(result);
      return result;
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : "Falha ao analisar anexo 3D.";
      setError(message);
      return null;
    } finally {
      setIsAnalyzing(false);
    }
  }

  return { analysis, isAnalyzing, error, analyze };
}
