import { apiClient } from "./client";
import type { SourceDocument, SourceProfile } from "./types";

export async function listSources(bookId: string): Promise<SourceDocument[]> {
  const res = await apiClient.get(`/books/${bookId}/sources`);
  return res.data;
}

export async function uploadSourceFile(
  bookId: string,
  file: File
): Promise<SourceDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiClient.post(`/books/${bookId}/sources/upload`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function registerSourceUrl(
  bookId: string,
  url: string
): Promise<SourceDocument> {
  const res = await apiClient.post(`/books/${bookId}/sources/url`, { url });
  return res.data;
}

export async function analyzeSource(
  sourceId: string,
  purpose?: string
): Promise<SourceProfile> {
  const res = await apiClient.post(`/sources/${sourceId}/analyze`, {
    purpose: purpose ?? null,
  });
  return res.data;
}

export async function getSourceProfile(sourceId: string): Promise<SourceProfile> {
  const res = await apiClient.get(`/sources/${sourceId}/profile`);
  return res.data;
}

export async function deleteSource(sourceId: string): Promise<void> {
  await apiClient.delete(`/sources/${sourceId}`);
}

export interface RegisterLocalDirResult {
  registered: SourceDocument[];
  skipped: string[];
  failed: { filename: string; error: string }[];
}

export async function registerLocalDir(
  bookId: string,
  dirPath: string,
  recursive: boolean
): Promise<RegisterLocalDirResult> {
  const res = await apiClient.post(`/books/${bookId}/sources/register-local-dir`, {
    dir_path: dirPath,
    recursive,
  });
  return res.data;
}
