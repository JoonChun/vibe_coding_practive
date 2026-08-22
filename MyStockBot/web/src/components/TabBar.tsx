import { NavLink } from "react-router-dom";

interface TabDef {
  to: string;
  label: string;
  end?: boolean;
  icon: JSX.Element;
}

const TABS: TabDef[] = [
  {
    to: "/",
    label: "메인",
    end: true,
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 13h4l3 7 4-14 3 7h4" />
      </svg>
    ),
  },
  {
    to: "/watchlist",
    label: "관심종목",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 3l2.5 5.5L20 9l-4 4 1 6-5-3-5 3 1-6-4-4 5.5-.5z" />
      </svg>
    ),
  },
  {
    to: "/paper",
    label: "모의투자",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 9h18M8 14h3" />
      </svg>
    ),
  },
  {
    to: "/alerts",
    label: "알림",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M18 8a6 6 0 10-12 0c0 6-2 8-2 8h16s-2-2-2-8" />
        <path d="M10.5 20a2 2 0 003 0" />
      </svg>
    ),
  },
];

/** 하단 고정 탭 네비게이션 (메인 / 관심종목 / 모의투자 / 알림). */
export function TabBar() {
  return (
    <nav className="tabbar" aria-label="주요 화면">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            "tabbar__tab" + (isActive ? " tabbar__tab--active" : "")
          }
        >
          <span className="tabbar__icon">{tab.icon}</span>
          <span className="tabbar__label">{tab.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
