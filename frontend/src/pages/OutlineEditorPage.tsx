import { useParams } from "react-router-dom";
import { OutlineEditor } from "./OutlineEditor";

export function OutlineEditorPage() {
  const { bookId } = useParams<{ bookId: string }>();

  if (!bookId) {
    return <div className="p-7 text-sm text-red-600">book_id가 없습니다.</div>;
  }

  return <OutlineEditor bookId={bookId} />;
}
