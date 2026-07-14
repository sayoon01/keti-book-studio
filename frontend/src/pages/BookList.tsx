import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { deleteBook, listBooks } from "../api/books";

export function BookList() {
  const queryClient = useQueryClient();
  const booksQuery = useQuery({ queryKey: ["books"], queryFn: listBooks });

  const deleteMutation = useMutation({
    mutationFn: deleteBook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["books"] }),
  });

  return (
    <div className="p-7">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-xl font-medium">책 관리</h1>
        <Link
          to="/books/new"
          className="text-sm font-medium px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white"
        >
          ＋ 새 책 만들기
        </Link>
      </div>

      {/* 책 상태(설정중/목차검토/작성중/완성) 필터는 book.status를 실제로 바꾸는
          로직이 백엔드에 아직 없어서(항상 draft_config) 지금은 넣지 않았다.
          transition_book_status() 붙이면 여기에 필터 탭을 추가한다. */}

      {booksQuery.isLoading && (
        <div className="text-sm text-slate-400">불러오는 중...</div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {booksQuery.data?.map((book) => (
          <div
            key={book.book_id}
            className="border border-slate-200 rounded-lg p-4 flex flex-col"
          >
            <div className="text-base font-medium mb-1">{book.title}</div>
            <div className="text-sm text-slate-400 mb-4">{book.status}</div>
            <div className="flex gap-2 mt-auto">
              <Link
                to={`/books/${book.book_id}/outline`}
                className="flex-1 text-center text-sm py-2 rounded-lg border border-slate-200 hover:bg-slate-50"
              >
                편집
              </Link>
              <button
                onClick={() => {
                  if (confirm(`"${book.title}"을(를) 삭제할까요?`)) {
                    deleteMutation.mutate(book.book_id);
                  }
                }}
                className="text-sm py-2 px-3 rounded-lg border border-red-200 text-red-600"
              >
                삭제
              </button>
            </div>
          </div>
        ))}
      </div>

      {booksQuery.data && booksQuery.data.length === 0 && (
        <div className="text-sm text-slate-400 border border-dashed border-slate-200 rounded-lg py-10 text-center">
          아직 만든 책이 없습니다.
        </div>
      )}
    </div>
  );
}
