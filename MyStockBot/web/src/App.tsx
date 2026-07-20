import { Route, Routes } from "react-router-dom";
import { TabLayout } from "./components/TabLayout";
import DashboardPage from "./pages/DashboardPage";
import MainDashboardPage from "./pages/MainDashboardPage";
import PaperTradingPage from "./pages/PaperTradingPage";
import StockDetailPage from "./pages/StockDetailPage";

export default function App() {
  return (
    <Routes>
      {/* 하단 탭바를 공유하는 3개 주요 화면 */}
      <Route element={<TabLayout />}>
        <Route path="/" element={<MainDashboardPage />} />
        <Route path="/watchlist" element={<DashboardPage />} />
        <Route path="/paper" element={<PaperTradingPage />} />
      </Route>
      {/* 상세는 탭바 없는 하위 화면 */}
      <Route path="/stocks/:code" element={<StockDetailPage />} />
    </Routes>
  );
}
