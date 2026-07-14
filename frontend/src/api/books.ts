import { apiClient } from "./client";
import { WORKSPACE_ID } from "../config";
import type { BookProject } from "./types";

export async function listBooks(): Promise<BookProject[]> {
  const res = await apiClient.get("/books", {
    params: { workspace_id: WORKSPACE_ID },
  });
  return res.data;
}

export async function createBook(title: string): Promise<BookProject> {
  const res = await apiClient.post("/books", {
    workspace_id: WORKSPACE_ID,
    title,
  });
  return res.data;
}

export async function getBook(bookId: string): Promise<BookProject> {
  const res = await apiClient.get(`/books/${bookId}`);
  return res.data;
}

export async function deleteBook(bookId: string): Promise<void> {
  await apiClient.delete(`/books/${bookId}`);
}
