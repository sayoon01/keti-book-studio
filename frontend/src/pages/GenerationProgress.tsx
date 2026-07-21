import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { generateChapterBody, getOutline } from "../api/outline";
import { ApiError } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { WizardStepper } from "../components/WizardStepper";
import type { BookUnit, UnitStatus } from "../api/types";

const DONE_STATUSES: UnitStatus[] = ["generated", "reviewed", "finalized"];

export function GenerationProgress({ bookId }: { bookId: string }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [runningAll, setRunningAll] = useState(false);
  const [currentUnitId, setCurrentUnitId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const outlineQuery = useQuery({
    queryKey: ["outline", bookId],
    queryFn: () => getOutline(bookId),
    enabled: !!bookId,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["outline", bookId] });

  if (outlineQuery.isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-base text-slate-500">
        불러오는 중...
      </div>
    );
  }
  if (outlineQuery.isError) {
    const err = outlineQuery.error;
    return (
      <div className="flex-1 flex items-center justify-center text-base text-red-600">
        불러오지 못했습니다: {err instanceof ApiError ? err.message : String(err)}
      </div>
    );
  }

  const { outline, units } = outlineQuery.data!;

  if (outline.status !== "approved") {
    return (
      <div className="flex flex-col flex-1 min-h-0">
        <div className="px-7 py-4 border-b border-slate-200 flex items-center gap-5">
          <span className="text-xl font-medium">새 책 만들기</span>
          <div className="ml-auto">
            <WizardStepper bookId={bookId} current="generate" />
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-base text-slate-500 mb-4">
              목차가 아직 승인되지 않았습니다. 먼저 목차를 승인해주세요.
            </p>
            <button
              onClick={() => navigate(`/books/${bookId}/outline`)}
              className="text-sm px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white"
            >
              목차로 이동
            </button>
          </div>
        </div>
      </div>
    );
  }

  const doneCount = units.filter((u) => DONE_STATUSES.includes(u.status)).length;
  const progressPct = units.length === 0 ? 0 : Math.round((doneCount / units.length) * 100);
  const pendingUnits = units.filter((u) => !DONE_STATUSES.includes(u.status));

  const generateOne = async (unit: BookUnit) => {
    setCurrentUnitId(unit.unit_id);
    try {
      await generateChapterBody(outline.outline_id, unit.unit_id);
    } catch (err) {
      setErrorMessage(
        `${unit.order}장 "${unit.title}" 생성 실패: ` +
          (err instanceof ApiError ? err.message : String(err))
      );
      throw err;
    } finally {
      invalidate();
    }
  };

  const generateAll = async () => {
    setRunningAll(true);
    setErrorMessage(null);
    for (const unit of pendingUnits) {
      try {
        await generateOne(unit);
      } catch {
        break;
      }
    }
    setCurrentUnitId(null);
    setRunningAll(false);
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-7 py-4 border-b border-slate-200 flex items-center gap-5">
        <span className="text-xl font-medium">새 책 만들기</span>
        <div className="ml-auto">
          <WizardStepper bookId={bookId} current="generate" />
        </div>
      </div>

      {errorMessage && (
        <div className="mx-7 mt-4 px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm flex items-center justify-between">
          {errorMessage}
          <button onClick={() => setErrorMessage(null)} className="ml-3 text-base shrink-0">
            ✕
          </button>
        </div>
      )}

      <div className="flex-1 p-7 overflow-auto">
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-base font-medium">
              전체 진행률 {doneCount} / {units.length}
            </span>
            <span className="text-sm text-slate-400">{progressPct}%</span>
          </div>
          <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-[var(--color-accent)] transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {pendingUnits.length > 0 && (
          <button
            onClick={generateAll}
            disabled={runningAll}
            className="w-full mb-6 text-base font-medium py-3 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-50"
          >
            {runningAll
              ? "생성 중... 챕터당 몇 분씩 걸릴 수 있습니다 (닫지 마세요)"
              : `남은 ${pendingUnits.length}개 챕터 전부 생성 시작`}
          </button>
        )}

        {pendingUnits.length === 0 && (
          <div className="mb-6 px-5 py-4 rounded-lg bg-[var(--color-status-done-bg)] text-[var(--color-status-done-text)] text-sm">
            모든 챕터 생성이 끝났습니다.
          </div>
        )}

        <div className="flex flex-col gap-2">
          {units.map((unit) => (
            <ChapterRow
              key={unit.unit_id}
              unit={unit}
              generating={currentUnitId === unit.unit_id}
              disabled={runningAll}
              onGenerate={() => generateOne(unit).catch(() => {})}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ChapterRow({
  unit,
  generating,
  disabled,
  onGenerate,
}: {
  unit: BookUnit;
  generating: boolean;
  disabled: boolean;
  onGenerate: () => void;
}) {
  const done = DONE_STATUSES.includes(unit.status);
  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${
        generating
          ? "border-[var(--color-accent)] bg-[var(--color-accent-light)]"
          : "border-slate-200 bg-white"
      }`}
    >
      <span className="text-sm text-slate-400 w-6">{unit.order}</span>
      <span className="flex-1 text-base">{unit.title}</span>
      <span className="text-sm text-slate-400">
        {unit.target_characters.toLocaleString()}자
      </span>
      {generating ? (
        <span className="text-sm text-[var(--color-accent)] flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full border-2 border-[var(--color-accent)] border-t-transparent animate-spin" />
          작성 중
        </span>
      ) : (
        <StatusBadge status={unit.status} />
      )}
      <button
        onClick={onGenerate}
        disabled={disabled || generating}
        className="text-sm px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 shrink-0"
      >
        {done ? "재생성" : "생성"}
      </button>
    </div>
  );
}
