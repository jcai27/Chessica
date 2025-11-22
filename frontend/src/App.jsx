import { Navigate, Route, Routes } from "react-router-dom";
import NavBar from "./components/NavBar";
import HomePage from "./pages/HomePage";
import ComputerPage from "./pages/ComputerPage";
import MultiplayerPage from "./pages/MultiplayerPage";
import ReplayPage from "./pages/ReplayPage";
import AuthPage from "./pages/AuthPage";

function App() {
  return (
    <div className="app-shell">
      <NavBar />
      <div className="app-body">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/computer" element={<ComputerPage />} />
          <Route path="/multiplayer" element={<MultiplayerPage />} />
          <Route path="/replay" element={<ReplayPage />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default App;
