import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { createBook } from "../api/books";

export function NewBook() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: () => createBook(title.trim()),
    onSuccess: (book) => navigate(`/books/${book.book_id}/sources`),
  });

  return (
    <div className="p-7 flex-1 flex flex-col">
      <h1 className="text-xl font-medium mb-1">새 책 만들기</h1>
      <p className="text-sm text-slate-500 mb-6">
        제목을 정하면 자료 업로드 단계로 이동합니다.
      </p>

      <div className="max-w-md flex flex-col gap-3">
        <label className="text-sm text-slate-600">책 제목</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && title.trim() && createMutation.mutate()}
          placeholder="예: ALD 공정 파라미터 기술서"
          className="border border-slate-300 rounded-lg px-4 py-3 text-base"
          autoFocus
        />
        <button
          onClick={() => createMutation.mutate()}
          disabled={!title.trim() || createMutation.isPending}
          className="bg-[var(--color-accent)] text-white text-base py-3 rounded-lg font-medium disabled:opacity-50"
        >
          {createMutation.isPending ? "만드는 중..." : "책 만들고 자료 업로드로 이동 →"}
        </button>
      </div>
    </div>
  );
}
