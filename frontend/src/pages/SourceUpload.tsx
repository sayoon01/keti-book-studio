import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  analyzeSource,
  deleteSource,
  getSourceProfile,
  listSources,
  registerLocalDir,
  registerSourceUrl,
  uploadSourceFile,
} from "../api/sources";
import { ApiError } from "../api/client";
import { WizardStepper } from "../components/WizardStepper";
import { DirectoryUploadSection } from "../components/DirectoryUploadSection";
import type { SourceDocument, SourceStatus } from "../api/types";

const STATUS_LABEL: Record<SourceStatus, string> = {
  uploaded: "업로드 완료",
  analyzing: "분석 중",
  analyzed: "분석 완료",
  failed: "분석 실패",
};

const STATUS_STYLE: Record<SourceStatus, string> = {
  uploaded: "bg-[var(--color-status-waiting-bg)] text-[var(--color-status-waiting-text)]",
  analyzing: "bg-[var(--color-status-writing-bg)] text-[var(--color-status-writing-text)]",
  analyzed: "bg-[var(--color-status-done-bg)] text-[var(--color-status-done-text)]",
  failed: "bg-[var(--color-status-failed-bg)] text-[var(--color-status-failed-text)]",
};

function isValidUrl(value: string): boolean {
  return /^https?:\/\//.test(value.trim());
}

export function SourceUpload({ bookId }: { bookId: string }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [urlInput, setUrlInput] = useState("");
  const [dirInput, setDirInput] = useState("");
  const [dirRecursive, setDirRecursive] = useState(false);
  const [showDirForm, setShowDirForm] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  const sourcesQuery = useQuery({
    queryKey: ["sources", bookId],
    queryFn: () => listSources(bookId),
    enabled: !!bookId,
  });

  const invalidateSources = () =>
    queryClient.invalidateQueries({ queryKey: ["sources", bookId] });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadSourceFile(bookId, file),
    onSuccess: (source) => {
      invalidateSources();
      analyzeMutation.mutate(source.source_id);
    },
    onError: (err) =>
      setErrorMessage(err instanceof ApiError ? err.message : "업로드에 실패했습니다."),
  });

  const registerUrlMutation = useMutation({
    mutationFn: (url: string) => registerSourceUrl(bookId, url),
    onSuccess: (source) => {
      setUrlInput("");
      invalidateSources();
      analyzeMutation.mutate(source.source_id);
    },
    onError: (err) =>
      setErrorMessage(err instanceof ApiError ? err.message : "URL 등록에 실패했습니다."),
  });

  const registerDirMutation = useMutation({
    mutationFn: () => registerLocalDir(bookId, dirInput.trim(), dirRecursive),
    onSuccess: (result) => {
      invalidateSources();
      setDirInput("");
      const parts = [`${result.registered.length}개 등록·분석 완료`];
      if (result.skipped.length > 0) parts.push(`${result.skipped.length}개 건너뜀(지원 안 하는 형식)`);
      if (result.failed.length > 0) parts.push(`${result.failed.length}개 실패`);
      setInfoMessage(parts.join(" · "));
      if (result.failed.length > 0) {
        setErrorMessage(
          result.failed.map((f) => `${f.filename}: ${f.error}`).join("\n")
        );
      }
    },
    onError: (err) =>
      setErrorMessage(
        err instanceof ApiError ? err.message : "폴더 등록에 실패했습니다."
      ),
  });

  const analyzeMutation = useMutation({
    mutationFn: (sourceId: string) => analyzeSource(sourceId),
    onSuccess: (_profile, sourceId) => {
      invalidateSources();
      setSelectedSourceId(sourceId);
    },
    onError: (err) =>
      setErrorMessage(err instanceof ApiError ? err.message : "분석에 실패했습니다."),
  });

  const deleteMutation = useMutation({
    mutationFn: (sourceId: string) => deleteSource(sourceId),
    onSuccess: (_void, sourceId) => {
      if (selectedSourceId === sourceId) setSelectedSourceId(null);
      invalidateSources();
    },
    onError: (err) =>
      setErrorMessage(err instanceof ApiError ? err.message : "삭제에 실패했습니다."),
  });

  const profileQuery = useQuery({
    queryKey: ["source-profile", selectedSourceId],
    queryFn: () => getSourceProfile(selectedSourceId!),
    enabled: !!selectedSourceId,
    retry: false,
  });

  const sources = sourcesQuery.data ?? [];
  const analyzedCount = sources.filter((s) => s.status === "analyzed").length;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-7 py-4 border-b border-slate-200 flex items-center gap-5">
        <span className="text-xl font-medium">새 책 만들기</span>
        <div className="ml-auto">
          <WizardStepper bookId={bookId} current="sources" />
        </div>
      </div>

      {errorMessage && (
        <div className="mx-7 mt-4 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm flex items-center justify-between whitespace-pre-line">
          {errorMessage}
          <button onClick={() => setErrorMessage(null)} className="ml-3 text-base shrink-0">
            ✕
          </button>
        </div>
      )}
      {infoMessage && (
        <div className="mx-7 mt-4 px-4 py-3 rounded-lg bg-[var(--color-accent-light)] text-[var(--color-accent)] text-sm flex items-center justify-between">
          {infoMessage}
          <button onClick={() => setInfoMessage(null)} className="ml-3 text-base">
            ✕
          </button>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="flex-1 p-7 overflow-auto border-r border-slate-200">
          <div className="text-base font-medium mb-3">자료 추가</div>

          <DirectoryUploadSection
            bookId={bookId}
            onUploaded={() => {
              invalidateSources();
              queryClient.invalidateQueries({
                queryKey: ["source-library", bookId],
              });
              setInfoMessage("폴더 자료를 자료 라이브러리에 등록했습니다.");
            }}
          />

          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files[0];
              if (file) uploadMutation.mutate(file);
            }}
            className="border-2 border-dashed border-slate-300 rounded-lg py-16 text-center cursor-pointer hover:bg-slate-50 hover:border-[var(--color-accent)] transition-colors mb-4"
          >
            <div className="text-3xl mb-2">📁</div>
            <div className="text-base text-slate-600 font-medium">
              파일을 드래그하거나 클릭하여 업로드하세요
            </div>
            <div className="text-sm text-slate-400 mt-1.5">
              PDF, DOCX, XLSX, CSV, MD, TXT
            </div>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadMutation.mutate(file);
                e.target.value = "";
              }}
            />
          </div>

          <div className="mb-1">
            <div className="flex gap-2">
              <input
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  isValidUrl(urlInput) &&
                  registerUrlMutation.mutate(urlInput.trim())
                }
                placeholder="https://example.com/article"
                className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm"
              />
              <button
                onClick={() => isValidUrl(urlInput) && registerUrlMutation.mutate(urlInput.trim())}
                disabled={!isValidUrl(urlInput) || registerUrlMutation.isPending}
                className="text-sm px-4 py-2 rounded-lg border border-slate-200 disabled:opacity-50"
              >
                추가
              </button>
            </div>
            {urlInput.trim() && !isValidUrl(urlInput) && (
              <p className="text-xs text-red-500 mt-1">
                웹 주소는 http:// 또는 https:// 로 시작해야 합니다. 서버 파일
                경로는 아래 "서버 폴더 경로로 여러 파일 한 번에 등록"을
                이용하세요.
              </p>
            )}
          </div>

          <button
            onClick={() => setShowDirForm((v) => !v)}
            className="text-sm text-slate-500 hover:text-[var(--color-accent)] hover:bg-slate-50 mb-3 px-3 py-1.5 rounded-lg border border-slate-200 inline-flex items-center gap-1.5"
          >
            <span className="text-xs">{showDirForm ? "▾" : "▸"}</span> 서버 폴더 경로로 여러 파일 한 번에 등록
          </button>

          {showDirForm && (
            <div className="border border-slate-200 rounded-lg p-3 mb-6 bg-slate-50">
              <label className="text-xs text-slate-500 block mb-1.5">
                서버(백엔드가 돌아가는 머신)의 폴더 경로
              </label>
              <input
                value={dirInput}
                onChange={(e) => setDirInput(e.target.value)}
                placeholder="/home/keti_spark1/사출기_데이터"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm mb-2"
              />
              <label className="flex items-center gap-1.5 text-xs text-slate-500 mb-3">
                <input
                  type="checkbox"
                  checked={dirRecursive}
                  onChange={(e) => setDirRecursive(e.target.checked)}
                />
                하위 폴더까지 포함
              </label>
              <button
                onClick={() => dirInput.trim() && registerDirMutation.mutate()}
                disabled={!dirInput.trim() || registerDirMutation.isPending}
                className="w-full text-sm py-2 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-50"
              >
                {registerDirMutation.isPending
                  ? "등록·분석 중... (파일 개수에 따라 오래 걸릴 수 있음)"
                  : "폴더 안 파일 전부 등록하고 분석"}
              </button>
            </div>
          )}

          <div className="text-sm font-medium mb-2">
            업로드된 자료 ({sources.length})
          </div>

          {sources.length === 0 && (
            <div className="text-sm text-slate-400 border border-dashed border-slate-200 rounded-lg py-8 text-center">
              아직 등록된 자료가 없습니다.
            </div>
          )}

          <div className="flex flex-col gap-2">
            {sources.map((source) => (
              <SourceRow
                key={source.source_id}
                source={source}
                active={source.source_id === selectedSourceId}
                onClick={() => setSelectedSourceId(source.source_id)}
                onReanalyze={() => analyzeMutation.mutate(source.source_id)}
                onDelete={() => {
                  if (confirm(`"${source.title}"을(를) 삭제할까요?`)) {
                    deleteMutation.mutate(source.source_id);
                  }
                }}
                reanalyzing={
                  analyzeMutation.isPending &&
                  analyzeMutation.variables === source.source_id
                }
              />
            ))}
          </div>

          {sources.length > 0 && (
            <div className="mt-8 border border-slate-200 rounded-lg p-5 bg-slate-50">
              <div className="text-sm font-medium text-slate-600 mb-2">
                💡 다음 단계
              </div>
              <p className="text-sm text-slate-500 leading-relaxed">
                자료를 더 추가하거나, 왼쪽 목록에서 자료를 눌러 분석 결과를
                확인해보세요. 최소 1개 이상 분석이 끝나면 &quot;다음: 책 설정&quot;으로
                넘어갈 수 있습니다. 여러 파일을 한 번에 넣고 싶다면 위의
                &quot;서버 폴더 경로로 여러 파일 한 번에 등록&quot;을 써보세요.
              </p>
            </div>
          )}
        </div>

        <div className="w-[380px] shrink-0 p-6 overflow-auto">
          <div className="text-base font-medium mb-3">AI 자료 분석</div>
          {!selectedSourceId && (
            <div className="text-sm text-slate-400 text-center pt-16">
              자료를 선택하면 분석 결과가 여기 나옵니다.
            </div>
          )}
          {selectedSourceId && profileQuery.isLoading && (
            <div className="text-sm text-slate-400">분석 결과를 불러오는 중...</div>
          )}
          {selectedSourceId && profileQuery.isError && (
            <div className="text-sm text-slate-400">
              아직 분석되지 않았거나 분석에 실패했습니다.
            </div>
          )}
          {profileQuery.data && (
            <div className="flex flex-col gap-4">
              <ProfileSection title="핵심 주제" items={profileQuery.data.main_topics} />
              <ProfileSection title="주요 근거" items={profileQuery.data.key_findings} />
              <ProfileSection title="부족한 내용" items={profileQuery.data.limitations} />
              <ProfileSection
                title="추천 활용"
                items={profileQuery.data.recommended_uses}
              />
              {profileQuery.data.summary && (
                <div>
                  <div className="text-sm font-medium text-slate-600 mb-1.5">요약</div>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    {profileQuery.data.summary}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="px-7 py-4 border-t border-slate-200 flex items-center justify-between">
        <span className="text-sm text-slate-500">
          분석 완료 {analyzedCount} / {sources.length}
        </span>
        <button
          onClick={() => navigate(`/books/${bookId}/config`)}
          disabled={analyzedCount === 0}
          className="text-base font-medium px-5 py-2.5 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-50"
        >
          다음: 책 설정 →
        </button>
      </div>
    </div>
  );
}

function SourceRow({
  source,
  active,
  onClick,
  onReanalyze,
  onDelete,
  reanalyzing,
}: {
  source: SourceDocument;
  active: boolean;
  onClick: () => void;
  onReanalyze: () => void;
  onDelete: () => void;
  reanalyzing: boolean;
}) {
  return (
    <div
      onClick={onClick}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer text-sm ${
        active
          ? "border-[var(--color-accent)] bg-[var(--color-accent-light)]"
          : "border-slate-200 bg-white hover:bg-slate-50"
      }`}
    >
      <span className="flex-1 truncate">{source.title}</span>
      <span className="text-xs text-slate-400 uppercase">{source.source_type}</span>
      <span
        className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLE[reanalyzing ? "analyzing" : source.status]}`}
      >
        {reanalyzing ? "분석 중" : STATUS_LABEL[source.status]}
      </span>
      {source.status !== "analyzing" && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onReanalyze();
          }}
          className="text-xs text-slate-400 hover:text-[var(--color-accent)]"
        >
          다시 분석
        </button>
      )}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="text-xs text-slate-400 hover:text-red-600"
      >
        삭제
      </button>
    </div>
  );
}

function ProfileSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <div className="text-sm font-medium text-slate-600 mb-1.5">{title}</div>
      <ul className="flex flex-col gap-1">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-slate-600 leading-relaxed">
            • {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
