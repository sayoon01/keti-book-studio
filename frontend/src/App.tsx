import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { OutlineEditor } from "./pages/OutlineEditor";

function App() {
  const [bookId, setBookId] = useState(
    () => localStorage.getItem("keti_book_id") ?? ""
  );
  const [draftId, setDraftId] = useState(bookId);

  const applyBookId = () => {
    setBookId(draftId.trim());
    localStorage.setItem("keti_book_id", draftId.trim());
  };

  return (
    <div className="flex h-screen bg-slate-100">
      <Sidebar />
      <div className="flex-1 overflow-auto p-6 flex justify-center">
        <div className="w-full max-w-[1320px] min-h-[calc(100vh-48px)] bg-white rounded-xl border border-slate-200 flex flex-col shadow-sm">
          {!bookId ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="flex flex-col gap-3 w-96">
                <label className="text-base text-slate-600">
                  Book ID (임시 - 책 관리 화면 붙기 전까지 직접 입력)
                </label>
                <input
                  value={draftId}
                  onChange={(e) => setDraftId(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && applyBookId()}
                  placeholder="book-xxxxxxxxxxxx"
                  className="border border-slate-300 rounded-lg px-4 py-3 text-base"
                />
                <button
                  onClick={applyBookId}
                  className="bg-[var(--color-accent)] text-white text-base py-3 rounded-lg font-medium"
                >
                  목차 편집기 열기
                </button>
              </div>
            </div>
          ) : (
            <OutlineEditor bookId={bookId} />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
