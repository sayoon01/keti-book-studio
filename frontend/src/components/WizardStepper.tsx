import { Link } from "react-router-dom";

type StepKey = "sources" | "config" | "outline" | "generate";

const STEPS: { key: StepKey; label: string; order: number }[] = [
  { key: "sources", label: "자료", order: 1 },
  { key: "config", label: "설정·페르소나", order: 2 },
  { key: "outline", label: "목차", order: 3 },
  { key: "generate", label: "생성", order: 4 },
];

export function WizardStepper({
  bookId,
  current,
}: {
  bookId: string;
  current: StepKey;
}) {
  const currentOrder = STEPS.find((s) => s.key === current)!.order;

  return (
    <div className="flex items-center gap-1.5 text-sm text-slate-500">
      {STEPS.map((step, i) => {
        const isCurrent = step.key === current;
        const isDone = step.order < currentOrder;
        return (
          <span key={step.key} className="flex items-center gap-1.5">
            {i > 0 && <span>›</span>}
            {isCurrent ? (
              <span className="text-[var(--color-accent)] font-medium">
                {step.order} {step.label}
              </span>
            ) : (
              <Link
                to={`/books/${bookId}/${step.key === "config" ? "config" : step.key}`}
                className={isDone ? "text-[var(--color-status-done-text)]" : ""}
              >
                {step.label}
              </Link>
            )}
          </span>
        );
      })}
    </div>
  );
}
