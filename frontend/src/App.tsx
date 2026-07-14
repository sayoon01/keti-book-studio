import { Outlet } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";

function App() {
  return (
    <div className="flex h-screen bg-slate-100">
      <Sidebar />
      <div className="flex-1 overflow-auto p-6 flex justify-center">
        <div className="w-full max-w-[1320px] min-h-[calc(100vh-48px)] bg-white rounded-xl border border-slate-200 flex flex-col shadow-sm">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

export default App;
