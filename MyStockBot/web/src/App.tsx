import { Route, Routes } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import StockDetailPage from "./pages/StockDetailPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/stocks/:code" element={<StockDetailPage />} />
    </Routes>
  );
}
