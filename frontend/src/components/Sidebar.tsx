import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "홈", icon: "🏠" },
  { to: "/books/new", label: "새 책 만들기", icon: "＋" },
  { to: "/books", label: "책 관리", icon: "📚" },
  { to: "/personas", label: "페르소나 관리", icon: "👤" },
  { to: "/runs", label: "실행 기록", icon: "🕐" },
];

export function Sidebar() {
  return (
    <aside className="w-[220px] shrink-0 bg-[var(--color-sidebar)] flex flex-col py-5">
      <div className="flex items-center gap-2 px-5 pb-6 text-white font-medium text-base">
        <span className="text-[var(--color-sidebar-active)]">⚡</span>
        KETI AI Studio
      </div>
      <nav className="flex flex-col gap-1 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-base ${
                isActive
                  ? "bg-[var(--color-sidebar-active)] text-white"
                  : "text-[var(--color-sidebar-text-dim)] hover:bg-[var(--color-sidebar-hover)]"
              }`
            }
          >
            <span className="w-5 text-center">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
