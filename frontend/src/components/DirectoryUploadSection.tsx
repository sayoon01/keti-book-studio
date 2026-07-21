import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { DirectoryUploadButton } from "./DirectoryUploadButton";
import {
  DirectoryUploadResult,
  uploadDirectory,
} from "../api/sourceLibrary";
import {
  formatBytes,
  summarizeDirectoryFiles,
} from "../utils/directoryFiles";

interface DirectoryUploadSectionProps {
  bookId: string;
  onUploaded?: (result: DirectoryUploadResult) => void;
}

export function DirectoryUploadSection({
  bookId,
  onUploaded,
}: DirectoryUploadSectionProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const summary = summarizeDirectoryFiles(files);

      return uploadDirectory({
        files,
        bookId,
        rootName: summary.rootName,
        collectionName: summary.rootName,
      });
    },
    onSuccess: (result) => {
      setSelectedFiles([]);
      onUploaded?.(result);
    },
  });

  const summary =
    selectedFiles.length > 0
      ? summarizeDirectoryFiles(selectedFiles)
      : null;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold">
            폴더 자료 추가
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            폴더 구조를 유지한 채 자료 라이브러리에 등록하고,
            현재 책과 연결합니다.
          </p>
        </div>

        <DirectoryUploadButton
          disabled={uploadMutation.isPending}
          onDirectorySelected={setSelectedFiles}
        />
      </div>

      {summary && (
        <div className="mt-4 rounded-lg bg-slate-50 p-4">
          <div className="font-medium">
            {summary.rootName}
          </div>

          <div className="mt-1 text-sm text-slate-600">
            파일 {summary.totalFiles.toLocaleString()}개 ·{" "}
            {formatBytes(summary.totalBytes)}
          </div>

          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() =>
                uploadMutation.mutate(selectedFiles)
              }
              disabled={uploadMutation.isPending}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {uploadMutation.isPending
                ? "업로드 중..."
                : "자료 라이브러리에 추가"}
            </button>

            <button
              type="button"
              onClick={() => setSelectedFiles([])}
              disabled={uploadMutation.isPending}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm"
            >
              취소
            </button>
          </div>
        </div>
      )}

      {uploadMutation.isError && (
        <p className="mt-3 text-sm text-red-600">
          {uploadMutation.error instanceof Error
            ? uploadMutation.error.message
            : "폴더 업로드에 실패했습니다."}
        </p>
      )}

      {uploadMutation.isSuccess && (
        <p className="mt-3 text-sm text-emerald-700">
          자료 {uploadMutation.data.uploaded_files}개를
          업로드했습니다.
        </p>
      )}
    </section>
  );
}
