import { apiClient } from "./client";

export type SourceCollectionStatus =
  | "CREATED"
  | "UPLOADING"
  | "UPLOADED"
  | "INDEXING"
  | "ANALYZING"
  | "READY"
  | "PARTIAL_FAILED"
  | "FAILED"
  | "DELETED";

export type SourceNodeType = "DIRECTORY" | "FILE";

export interface SourceCollection {
  id: string;
  name: string;
  description: string | null;

  collection_type: string;
  status: SourceCollectionStatus;
  root_name: string | null;

  total_files: number;
  supported_files: number;
  skipped_files: number;
  failed_files: number;
  total_size_bytes: number;

  summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceTreeNode {
  id: string;
  node_type: SourceNodeType;
  name: string;
  relative_path: string;
  status: string;

  document_id: string | null;
  size_bytes: number;
  extension: string | null;
  error_message: string | null;

  children: SourceTreeNode[];
}

export interface SourceCollectionTreeResponse {
  collection: SourceCollection;
  roots: SourceTreeNode[];
}

export interface DirectoryUploadInput {
  files: File[];
  collectionName: string;
  rootName: string;
  description?: string;
  bookId?: string;
}

export interface DirectoryUploadResult {
  collection: SourceCollection;
  uploaded_files: number;
  skipped_files: number;
  failed_files: number;
  warnings: string[];
}

export interface BookSourceCollectionLink {
  id: string;
  book_id: string;
  collection_id: string;
  enabled: boolean;
  purpose: string | null;
  priority: number;
  linked_by: string;
  created_at: string;
  updated_at: string;
}

export async function uploadDirectory(
  input: DirectoryUploadInput,
): Promise<DirectoryUploadResult> {
  if (input.files.length === 0) {
    throw new Error("업로드할 파일이 없습니다.");
  }

  const formData = new FormData();

  for (const file of input.files) {
    const relativePath =
      file.webkitRelativePath || file.name;

    formData.append("files", file);
    formData.append("relative_paths", relativePath);
  }

  formData.append("collection_name", input.collectionName);
  formData.append("root_name", input.rootName);

  if (input.description) {
    formData.append("description", input.description);
  }

  if (input.bookId) {
    formData.append("book_id", input.bookId);
  }

  const response = await apiClient.post<DirectoryUploadResult>(
    "/source-library/collections/directory",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );

  return response.data;
}

export async function getSourceCollections(): Promise<
  SourceCollection[]
> {
  const response = await apiClient.get<SourceCollection[]>(
    "/source-library/collections",
  );

  return response.data;
}

export async function getCollectionTree(
  collectionId: string,
): Promise<SourceCollectionTreeResponse> {
  const response =
    await apiClient.get<SourceCollectionTreeResponse>(
      `/source-library/collections/${collectionId}/tree`,
    );

  return response.data;
}

export async function linkCollectionToBook(
  bookId: string,
  collectionId: string,
  payload?: {
    purpose?: string;
    priority?: number;
  },
): Promise<BookSourceCollectionLink> {
  const response =
    await apiClient.post<BookSourceCollectionLink>(
      `/source-library/books/${bookId}/collections/${collectionId}`,
      {
        purpose: payload?.purpose ?? null,
        priority: payload?.priority ?? 0,
      },
    );

  return response.data;
}

export async function getBookSourceCollections(
  bookId: string,
): Promise<BookSourceCollectionLink[]> {
  const response =
    await apiClient.get<BookSourceCollectionLink[]>(
      `/source-library/books/${bookId}/collections`,
    );

  return response.data;
}

export async function unlinkCollectionFromBook(
  bookId: string,
  collectionId: string,
): Promise<void> {
  await apiClient.delete(
    `/source-library/books/${bookId}/collections/${collectionId}`,
  );
}
