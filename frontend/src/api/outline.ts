import { apiClient } from "./client";
import type {
  BookConfig,
  BookUnit,
  BookUnitUpdatePayload,
  ChapterProposal,
  OutlineWithUnits,
} from "./types";

export async function getOutline(bookId: string): Promise<OutlineWithUnits> {
  const res = await apiClient.get(`/books/${bookId}/outline`);
  return res.data;
}

export async function getConfig(bookId: string): Promise<BookConfig> {
  const res = await apiClient.get(`/books/${bookId}/config`);
  return res.data;
}

export async function generateOutline(
  bookId: string,
  chapterCount?: number
): Promise<OutlineWithUnits> {
  const res = await apiClient.post(`/books/${bookId}/outline/generate`, {
    chapter_count: chapterCount ?? 0,
  });
  return res.data;
}

export async function previewOutline(
  bookId: string,
  chapterCount?: number
): Promise<ChapterProposal[]> {
  const res = await apiClient.post(`/books/${bookId}/outline/generate`, {
    chapter_count: chapterCount ?? 0,
    dry_run: true,
  });
  return res.data.chapters;
}

export async function approveOutline(bookId: string) {
  const res = await apiClient.post(`/books/${bookId}/outline/approve`);
  return res.data;
}

export async function updateUnit(
  outlineId: string,
  unitId: string,
  payload: BookUnitUpdatePayload
): Promise<BookUnit> {
  const res = await apiClient.patch(
    `/outlines/${outlineId}/units/${unitId}`,
    payload
  );
  return res.data;
}

export async function createUnit(
  outlineId: string,
  title: string
): Promise<BookUnit> {
  const res = await apiClient.post(`/outlines/${outlineId}/units`, {
    title,
    target_characters: 5000,
  });
  return res.data;
}

export async function deleteUnit(outlineId: string, unitId: string) {
  await apiClient.delete(`/outlines/${outlineId}/units/${unitId}`);
}

export async function generateChapterBody(outlineId: string, unitId: string) {
  const res = await apiClient.post(
    `/outlines/${outlineId}/units/${unitId}/generate`
  );
  return res.data;
}
