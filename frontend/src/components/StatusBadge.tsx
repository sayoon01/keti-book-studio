import type { UnitStatus } from "../api/types";

const STATUS_LABEL: Record<UnitStatus, string> = {
  draft: "대기",
  edited: "수정됨",
  approved: "승인됨",
  generating: "작성 중",
  generated: "작성 완료",
  reviewed: "검토 완료",
  finalized: "확정",
};

const STATUS_STYLE: Record<UnitStatus, string> = {
  draft: "bg-[var(--color-status-waiting-bg)] text-[var(--color-status-waiting-text)]",
  edited: "bg-[var(--color-status-waiting-bg)] text-[var(--color-status-waiting-text)]",
  approved: "bg-[var(--color-status-writing-bg)] text-[var(--color-status-writing-text)]",
  generating: "bg-[var(--color-status-writing-bg)] text-[var(--color-status-writing-text)]",
  generated: "bg-[var(--color-status-done-bg)] text-[var(--color-status-done-text)]",
  reviewed: "bg-[var(--color-status-done-bg)] text-[var(--color-status-done-text)]",
  finalized: "bg-[var(--color-status-done-bg)] text-[var(--color-status-done-text)]",
};

export function StatusBadge({ status }: { status: UnitStatus }) {
  return (
    <span
      className={`text-xs px-2.5 py-1 rounded-md font-medium ${STATUS_STYLE[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}
