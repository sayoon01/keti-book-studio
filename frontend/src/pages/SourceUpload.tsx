import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  analyzeSource,
  deleteSource,
  getSourceProfile,
  listSources,
  registerSourceUrl,
  uploadSourceFile,
} from "../api/sources";
import { ApiError } from "../api/client";
import { WizardStepper } from "../components/WizardStepper";
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

export function SourceUpload({ bookId }: { bookId: string }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [urlInput, setUrlInput] = useState("");
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const sourcesQuery = useQuery({
    queryKey: ["sources", bookId],
    queryFn: () => listSources(bookId),
    enabled: !!bookId,
  });

  const invalidateSources = () =>
    queryClient.invalidateQueries({ queryKey: ["sources", bookId] });

  const analyzeMutation = useMutation({
    mutationFn: (sourceId: string) => analyzeSource(sourceId),
    onSuccess: (_profile, sourceId) => {
      invalidateSources();
      setSelectedSourceId(sourceId);
    },
    onError: (err) =>
      setErrorMessage(err instanceof ApiError ? err.message : "분석에 실패했습니다."),
  });

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
        <div className="mx-7 mt-4 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm flex items-center justify-between">
          {errorMessage}
          <button onClick={() => setErrorMessage(null)} className="ml-3 text-base">
            ✕
          </button>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="flex-1 p-7 overflow-auto border-r border-slate-200">
          <div className="text-base font-medium mb-3">자료 추가</div>

          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files[0];
              if (file) uploadMutation.mutate(file);
            }}
            className="border-2 border-dashed border-slate-300 rounded-lg py-10 text-center cursor-pointer hover:bg-slate-50 mb-3"
          >
            <div className="text-sm text-slate-500">
              파일을 드래그하거나 클릭하여 업로드하세요
            </div>
            <div className="text-xs text-slate-400 mt-1">
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

          <div className="flex gap-2 mb-6">
            <input
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) =>
                e.key === "Enter" && urlInput.trim() && registerUrlMutation.mutate(urlInput.trim())
              }
              placeholder="https://example.com/article"
              className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
            <button
              onClick={() => urlInput.trim() && registerUrlMutation.mutate(urlInput.trim())}
              disabled={!urlInput.trim() || registerUrlMutation.isPending}
              className="text-sm px-4 py-2 rounded-lg border border-slate-200 disabled:opacity-50"
            >
              추가
            </button>
          </div>

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
