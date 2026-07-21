export interface DirectoryFileSummary {
  rootName: string;
  totalFiles: number;
  totalBytes: number;
  extensionCounts: Record<string, number>;
}

export function summarizeDirectoryFiles(
  files: File[],
): DirectoryFileSummary {
  const firstRelativePath =
    files[0]?.webkitRelativePath || files[0]?.name || "";

  const rootName =
    firstRelativePath.split("/")[0] || "업로드 자료";

  const extensionCounts: Record<string, number> = {};
  let totalBytes = 0;

  for (const file of files) {
    totalBytes += file.size;

    const extensionMatch = file.name
      .toLowerCase()
      .match(/(\.[^.]+)$/);

    const extension = extensionMatch?.[1] ?? "(확장자 없음)";

    extensionCounts[extension] =
      (extensionCounts[extension] ?? 0) + 1;
  }

  return {
    rootName,
    totalFiles: files.length,
    totalBytes,
    extensionCounts,
  };
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );

  const value = bytes / 1024 ** index;

  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
