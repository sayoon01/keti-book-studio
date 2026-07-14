import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getConfig } from "../api/outline";
import { listPersonas, setBookPersona, suggestConfig, updateConfig } from "../api/config";
import { getBook } from "../api/books";
import { ApiError } from "../api/client";
import { WizardStepper } from "../components/WizardStepper";
import type { BookConfigUpdatePayload, Persona } from "../api/types";

export function ConfigPersona({ bookId }: { bookId: string }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  const bookQuery = useQuery({ queryKey: ["book", bookId], queryFn: () => getBook(bookId) });
  const configQuery = useQuery({
    queryKey: ["config", bookId],
    queryFn: () => getConfig(bookId),
  });
  const personasQuery = useQuery({ queryKey: ["personas"], queryFn: listPersonas });

  const [form, setForm] = useState<BookConfigUpdatePayload>({});

  useEffect(() => {
    if (!configQuery.data) return;
    setForm({
      document_type: configQuery.data.document_type,
      target_reader: configQuery.data.target_reader,
      purpose: configQuery.data.purpose,
      tone: configQuery.data.tone,
      expertise_level: configQuery.data.expertise_level,
      default_chars_per_chapter: configQuery.data.default_chars_per_chapter,
      citation_policy: configQuery.data.citation_policy,
      visual_density: configQuery.data.visual_density,
      approval_mode: configQuery.data.approval_mode,
    });
  }, [configQuery.data]);

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["config", bookId] });
    queryClient.invalidateQueries({ queryKey: ["book", bookId] });
  };

  const saveMutation = useMutation({
    mutationFn: () => updateConfig(bookId, form),
    onSuccess: () => {
      invalidateAll();
      setInfoMessage("설정을 저장했습니다.");
    },
    onError: (err) =>
      setErrorMessage(err instanceof ApiError ? err.message : "저장에 실패했습니다."),
  });

  const suggestMutation = useMutation({
    mutationFn: () => suggestConfig(bookId),
    onSuccess: () => {
      invalidateAll();
      setInfoMessage("AI 추천값이 반영되었습니다.");
    },
    onError: (err) =>
      setErrorMessage(
        err instanceof ApiError ? err.message : "추천 생성에 실패했습니다."
      ),
  });

  const personaMutation = useMutation({
    mutationFn: (personaId: string) => setBookPersona(bookId, personaId),
    onSuccess: invalidateAll,
    onError: (err) =>
      setErrorMessage(err instanceof ApiError ? err.message : "페르소나 선택에 실패했습니다."),
  });

  if (configQuery.isLoading || bookQuery.isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-base text-slate-500">
        불러오는 중...
      </div>
    );
  }

  const personas = personasQuery.data ?? [];
  const selectedPersonaId = bookQuery.data?.persona_id ?? null;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-7 py-4 border-b border-slate-200 flex items-center gap-5">
        <span className="text-xl font-medium">새 책 만들기</span>
        <div className="ml-auto">
          <WizardStepper bookId={bookId} current="config" />
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
      {infoMessage && (
        <div className="mx-7 mt-4 px-4 py-3 rounded-lg bg-[var(--color-accent-light)] text-[var(--color-accent)] text-sm flex items-center justify-between">
          {infoMessage}
          <button onClick={() => setInfoMessage(null)} className="ml-3 text-base">
            ✕
          </button>
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-auto">
        <div className="flex-1 p-7 border-r border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <span className="text-base font-medium">책 설정</span>
            <button
              onClick={() => suggestMutation.mutate()}
              disabled={suggestMutation.isPending}
              className="text-sm px-3.5 py-2 rounded-lg border border-slate-200 flex items-center gap-2 disabled:opacity-50 hover:bg-slate-50"
            >
              ✨ {suggestMutation.isPending ? "추천 받는 중..." : "AI 설정 추천받기"}
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <Field label="책 유형">
              <input
                value={form.document_type ?? ""}
                onChange={(e) => setForm({ ...form, document_type: e.target.value })}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                placeholder="예: technical_guide"
              />
            </Field>
            <Field label="대상 독자">
              <input
                value={form.target_reader ?? ""}
                onChange={(e) => setForm({ ...form, target_reader: e.target.value })}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                placeholder="예: 반도체 공정 엔지니어"
              />
            </Field>
          </div>

          <Field label="책의 목적">
            <textarea
              value={form.purpose ?? ""}
              onChange={(e) => setForm({ ...form, purpose: e.target.value })}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm min-h-[70px] resize-none mb-4"
            />
          </Field>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <Field label="문체·톤">
              <input
                value={form.tone ?? ""}
                onChange={(e) => setForm({ ...form, tone: e.target.value })}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                placeholder="예: 전문적이고 명확하게"
              />
            </Field>
            <Field label="전문성 수준">
              <input
                value={form.expertise_level ?? ""}
                onChange={(e) => setForm({ ...form, expertise_level: e.target.value })}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                placeholder="예: intermediate"
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <Field label="목차당 기본 글자 수">
              <input
                type="number"
                value={form.default_chars_per_chapter ?? 0}
                onChange={(e) =>
                  setForm({ ...form, default_chars_per_chapter: Number(e.target.value) })
                }
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              />
            </Field>
            <Field label="시각자료 밀도">
              <select
                value={form.visual_density ?? "medium"}
                onChange={(e) => setForm({ ...form, visual_density: e.target.value })}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="low">낮음</option>
                <option value="medium">보통</option>
                <option value="high">높음</option>
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-5">
            <Field label="인용 정책">
              <input
                value={form.citation_policy ?? ""}
                onChange={(e) => setForm({ ...form, citation_policy: e.target.value })}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                placeholder="예: source_required"
              />
            </Field>
            <Field label="승인 모드">
              <select
                value={form.approval_mode ?? "balanced"}
                onChange={(e) =>
                  setForm({
                    ...form,
                    approval_mode: e.target.value as BookConfigUpdatePayload["approval_mode"],
                  })
                }
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="safe">안전 (전부 확인)</option>
                <option value="balanced">균형</option>
                <option value="auto">자동</option>
              </select>
            </Field>
          </div>

          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="text-sm px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-50"
          >
            {saveMutation.isPending ? "저장 중..." : "설정 저장"}
          </button>
        </div>

        <div className="w-[360px] shrink-0 p-6 overflow-auto">
          <div className="text-base font-medium mb-3">페르소나 선택</div>
          <div className="flex flex-col gap-2">
            {personas.map((persona) => (
              <PersonaCard
                key={persona.persona_id}
                persona={persona}
                selected={persona.persona_id === selectedPersonaId}
                onSelect={() => personaMutation.mutate(persona.persona_id)}
              />
            ))}
          </div>
          {personas.length === 0 && (
            <div className="text-sm text-slate-400">페르소나를 불러오는 중...</div>
          )}
        </div>
      </div>

      <div className="px-7 py-4 border-t border-slate-200 flex items-center justify-between">
        <span className="text-sm text-slate-500">
          {selectedPersonaId ? "페르소나 선택됨" : "페르소나를 선택해야 목차를 만들 수 있습니다"}
        </span>
        <button
          onClick={() => navigate(`/books/${bookId}/outline`)}
          disabled={!selectedPersonaId}
          className="text-base font-medium px-5 py-2.5 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-50"
        >
          다음: 목차 만들기 →
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="text-sm text-slate-500 block mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function PersonaCard({
  persona,
  selected,
  onSelect,
}: {
  persona: Persona;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`px-4 py-3 rounded-lg border cursor-pointer ${
        selected
          ? "border-[var(--color-accent)] bg-[var(--color-accent-light)]"
          : "border-slate-200 bg-white hover:bg-slate-50"
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">{persona.name}</span>
        {persona.scope === "system" && (
          <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-500">
            기본
          </span>
        )}
      </div>
      {persona.defaults?.description && (
        <p className="text-xs text-slate-500 leading-relaxed">
          {persona.defaults.description}
        </p>
      )}
    </div>
  );
}
