import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listBooks } from "../api/books";

export function Home() {
  const booksQuery = useQuery({ queryKey: ["books"], queryFn: listBooks });

  return (
    <div className="p-7">
      <h1 className="text-xl font-medium mb-1">AI 작업공간</h1>
      <p className="text-sm text-slate-500 mb-6">
        책을 만들거나 이어서 편집하세요.
      </p>

      <div className="flex items-center justify-between mb-4">
        <span className="text-base font-medium">최근 책</span>
        <Link
          to="/books"
          className="text-sm text-[var(--color-accent)] hover:underline"
        >
          책 관리 전체 보기 →
        </Link>
      </div>

      {booksQuery.isLoading && (
        <div className="text-sm text-slate-400">불러오는 중...</div>
      )}

      {booksQuery.data && booksQuery.data.length === 0 && (
        <div className="text-sm text-slate-400 border border-dashed border-slate-200 rounded-lg py-10 text-center">
          아직 만든 책이 없습니다.{" "}
          <Link to="/books/new" className="text-[var(--color-accent)]">
            새 책 만들기
          </Link>
          로 시작해보세요.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        {booksQuery.data?.slice(0, 6).map((book) => (
          <Link
            key={book.book_id}
            to={`/books/${book.book_id}/outline`}
            className="border border-slate-200 rounded-lg p-4 hover:border-[var(--color-accent)] transition-colors"
          >
            <div className="text-base font-medium mb-1">{book.title}</div>
            <div className="text-sm text-slate-400">{book.status}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
