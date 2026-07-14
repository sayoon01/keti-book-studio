import { useParams } from "react-router-dom";
import { ConfigPersona } from "./ConfigPersona";

export function ConfigPersonaPage() {
  const { bookId } = useParams<{ bookId: string }>();

  if (!bookId) {
    return <div className="p-7 text-sm text-red-600">book_id가 없습니다.</div>;
  }

  return <ConfigPersona bookId={bookId} />;
}
