import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveOutline,
  createUnit,
  deleteUnit,
  generateOutline,
  getOutline,
  updateUnit,
} from "../api/outline";
import { ApiError } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { WizardStepper } from "../components/WizardStepper";
import type { BookUnit } from "../api/types";

export function OutlineEditor({ bookId }: { bookId: string }) {
  const queryClient = useQueryClient();
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const outlineQuery = useQuery({
    queryKey: ["outline", bookId],
    queryFn: () => getOutline(bookId),
    enabled: !!bookId,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["outline", bookId] });

  const updateMutation = useMutation({
    mutationFn: ({
      unitId,
      payload,
    }: {
      unitId: string;
      payload: Parameters<typeof updateUnit>[2];
    }) => updateUnit(outlineQuery.data!.outline.outline_id, unitId, payload),
    onSuccess: invalidate,
    onError: (err) =>
      setErrorMessage(err instanceof ApiError ? err.message : "수정에 실패했습니다."),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createUnit(outlineQuery.data!.outline.outline_id, "새 챕터"),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (unitId: string) =>
      deleteUnit(outlineQuery.data!.outline.outline_id, unitId),
    onSuccess: () => {
      setSelectedUnitId(null);
      invalidate();
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => generateOutline(bookId),
    onSuccess: invalidate,
    onError: (err) =>
      setErrorMessage(
        err instanceof ApiError ? err.message : "목차 생성에 실패했습니다."
      ),
  });

  const approveMutation = useMutation({
    mutationFn: () => approveOutline(bookId),
    onSuccess: invalidate,
    onError: (err) =>
      setErrorMessage(
        err instanceof ApiError ? err.message : "승인에 실패했습니다."
      ),
  });

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
        목차를 불러오지 못했습니다:{" "}
        {err instanceof ApiError ? err.message : String(err)}
      </div>
    );
  }

  const { outline, units } = outlineQuery.data!;
  const selectedUnit = units.find((u) => u.unit_id === selectedUnitId) ?? null;
  const totalChars = units.reduce((sum, u) => sum + u.target_characters, 0);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-7 py-4 border-b border-slate-200 flex items-center gap-5">
        <span className="text-xl font-medium">새 책 만들기</span>
        <div className="ml-auto">
          <WizardStepper bookId={bookId} current="outline" />
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
          <div className="flex items-center justify-between mb-4">
            <span className="font-medium text-base">
              목차 구성 ({units.length}개 챕터)
              {outline.status === "approved" && (
                <span className="ml-2 text-sm text-[var(--color-status-done-text)]">
                  승인됨
                </span>
              )}
            </span>
            <button
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
              className="text-sm px-3.5 py-2 rounded-lg border border-slate-200 flex items-center gap-2 disabled:opacity-50 hover:bg-slate-50"
            >
              ✨ {generateMutation.isPending ? "생성 중..." : "AI 목차 생성"}
            </button>
          </div>

          {units.length === 0 && (
            <div className="text-sm text-slate-400 text-center py-10 border border-dashed border-slate-200 rounded-lg mb-3">
              아직 챕터가 없습니다. 직접 추가하거나 AI 목차 생성을 눌러보세요.
            </div>
          )}

          <div className="flex flex-col gap-2">
            {units.map((unit) => (
              <UnitRow
                key={unit.unit_id}
                unit={unit}
                active={unit.unit_id === selectedUnitId}
                onClick={() => setSelectedUnitId(unit.unit_id)}
              />
            ))}
          </div>

          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="w-full mt-3 text-sm py-2.5 rounded-lg border border-dashed border-slate-300 text-slate-500 hover:bg-slate-50"
          >
            ＋ 챕터 추가
          </button>
        </div>

        <div className="w-[360px] shrink-0 p-6 overflow-auto">
          {selectedUnit ? (
            <UnitDetailPanel
              unit={selectedUnit}
              onSave={(payload) =>
                updateMutation.mutate({ unitId: selectedUnit.unit_id, payload })
              }
              onDelete={() => deleteMutation.mutate(selectedUnit.unit_id)}
              saving={updateMutation.isPending}
            />
          ) : (
            <div className="text-sm text-slate-400 text-center pt-16">
              챕터를 선택하면 상세 정보가 여기 나옵니다.
            </div>
          )}
        </div>
      </div>

      <div className="px-7 py-4 border-t border-slate-200 flex items-center justify-between">
        <span className="text-sm text-slate-500">
          예상 총 분량 {totalChars.toLocaleString()}자
        </span>
        <button
          onClick={() => approveMutation.mutate()}
          disabled={approveMutation.isPending || units.length === 0}
          className="text-base font-medium px-5 py-2.5 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-50"
        >
          {approveMutation.isPending ? "승인 중..." : "목차 승인하고 생성 시작 →"}
        </button>
      </div>
    </div>
  );
}

function UnitRow({
  unit,
  active,
  onClick,
}: {
  unit: BookUnit;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer text-base ${
        active
          ? "border-[var(--color-accent)] bg-[var(--color-accent-light)]"
          : "border-slate-200 bg-white hover:bg-slate-50"
      }`}
    >
      <span className="text-slate-400 text-sm w-5">{unit.order}</span>
      <span className={`flex-1 ${active ? "font-medium" : ""}`}>{unit.title}</span>
      <span className="text-sm text-slate-400">
        {unit.target_characters.toLocaleString()}자
      </span>
      <StatusBadge status={unit.status} />
    </div>
  );
}

function UnitDetailPanel({
  unit,
  onSave,
  onDelete,
  saving,
}: {
  unit: BookUnit;
  onSave: (payload: { title: string; description: string; target_characters: number }) => void;
  onDelete: () => void;
  saving: boolean;
}) {
  const [title, setTitle] = useState(unit.title);
  const [description, setDescription] = useState(unit.description);
  const [targetChars, setTargetChars] = useState(unit.target_characters);

  const dirty =
    title !== unit.title ||
    description !== unit.description ||
    targetChars !== unit.target_characters;

  return (
    <div key={unit.unit_id}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-slate-400">{unit.order}장</span>
        <StatusBadge status={unit.status} />
      </div>

      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full font-medium text-base mb-4 border-0 border-b border-transparent focus:border-slate-300 outline-none px-0 py-1.5"
      />

      <label className="text-sm text-slate-500 block mb-1.5">챕터 설명</label>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        className="w-full text-sm min-h-[80px] resize-none border border-slate-200 rounded-lg p-3 mb-4"
      />

      <label className="text-sm text-slate-500 block mb-1.5">목표 글자 수</label>
      <input
        type="number"
        value={targetChars}
        onChange={(e) => setTargetChars(Number(e.target.value))}
        className="w-full text-base border border-slate-200 rounded-lg px-3 py-2 mb-5"
      />

      <div className="flex gap-2">
        <button
          onClick={() => onSave({ title, description, target_characters: targetChars })}
          disabled={!dirty || saving}
          className="flex-1 text-sm py-2.5 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-40"
        >
          {saving ? "저장 중..." : "저장"}
        </button>
        <button
          onClick={onDelete}
          className="text-sm py-2.5 px-4 rounded-lg border border-red-200 text-red-600"
        >
          삭제
        </button>
      </div>
    </div>
  );
}
