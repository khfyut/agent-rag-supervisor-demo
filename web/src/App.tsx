import { Navigate, Route, Routes } from "react-router-dom";
import AskPage from "./pages/AskPage";
import ArchPage from "./pages/ArchPage";
import EvalPage from "./pages/EvalPage";
import KbPage from "./pages/KbPage";
import MonitorPage from "./pages/MonitorPage";

// 路由接线：五页导航（/ask 问答演示 /eval 评估看板 /kb 知识库 /arch 架构讲解 /monitor 数据监测）
export default function App() {
  return (
    <Routes>
      <Route path="/ask" element={<AskPage />} />
      <Route path="/eval" element={<EvalPage />} />
      <Route path="/kb" element={<KbPage />} />
      <Route path="/arch" element={<ArchPage />} />
      <Route path="/monitor" element={<MonitorPage />} />
      <Route path="*" element={<Navigate to="/ask" replace />} />
    </Routes>
  );
}
