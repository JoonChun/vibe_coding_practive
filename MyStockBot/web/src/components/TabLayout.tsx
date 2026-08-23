import { Outlet } from "react-router-dom";
import { TabBar } from "./TabBar";

/** 주요 화면(메인/관심종목/모의투자/알림)을 감싸는 레이아웃 — 하단 탭바 고정. */
export function TabLayout() {
  return (
    <div className="tab-layout">
      <Outlet />
      <TabBar />
    </div>
  );
}
