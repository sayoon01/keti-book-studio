import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import App from "./App.tsx";
import { Home } from "./pages/Home.tsx";
import { BookList } from "./pages/BookList.tsx";
import { NewBook } from "./pages/NewBook.tsx";
import { OutlineEditorPage } from "./pages/OutlineEditorPage.tsx";
import { SourceUploadPage } from "./pages/SourceUploadPage.tsx";
import { ConfigPersonaPage } from "./pages/ConfigPersonaPage.tsx";
import { ComingSoon } from "./pages/ComingSoon.tsx";

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />}>
            <Route index element={<Home />} />
            <Route path="books" element={<BookList />} />
            <Route path="books/new" element={<NewBook />} />
            <Route path="books/:bookId/sources" element={<SourceUploadPage />} />
            <Route path="books/:bookId/config" element={<ConfigPersonaPage />} />
            <Route path="books/:bookId/outline" element={<OutlineEditorPage />} />
            <Route path="personas" element={<ComingSoon label="페르소나 관리" />} />
            <Route path="runs" element={<ComingSoon label="실행 기록" />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
