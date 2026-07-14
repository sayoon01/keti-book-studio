import { apiClient } from "./client";
import type {
  BookConfig,
  BookConfigUpdatePayload,
  ConfigSuggestResult,
  Persona,
} from "./types";

export async function updateConfig(
  bookId: string,
  payload: BookConfigUpdatePayload
): Promise<BookConfig> {
  const res = await apiClient.patch(`/books/${bookId}/config`, payload);
  return res.data;
}

export async function suggestConfig(bookId: string): Promise<ConfigSuggestResult> {
  const res = await apiClient.post(`/books/${bookId}/config/suggest`, {});
  return res.data;
}

export async function listPersonas(): Promise<Persona[]> {
  const res = await apiClient.get("/personas");
  return res.data;
}

export async function setBookPersona(
  bookId: string,
  personaId: string
): Promise<void> {
  await apiClient.patch(`/books/${bookId}`, { persona_id: personaId });
}
