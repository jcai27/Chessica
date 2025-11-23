import { Navigate, Route, Routes } from "react-router-dom";
import { SettingsProvider } from "./lib/settings";
import NavBar from "./components/NavBar";
import TutorialModal from "./components/TutorialModal";
import HomePage from "./pages/HomePage";
import ComputerPage from "./pages/ComputerPage";
import MultiplayerPage from "./pages/MultiplayerPage";
import ReplayPage from "./pages/ReplayPage";
import AuthPage from "./pages/AuthPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import SettingsPage from "./pages/SettingsPage";
import "./pages/SettingsPage.css";

function App() {
  return (
    <SettingsProvider>
      <div className="app-shell">
        <NavBar />
        <TutorialModal />
        <div className="app-body">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/computer" element={<ComputerPage />} />
            <Route path="/multiplayer" element={<MultiplayerPage />} />
            <Route path="/replay" element={<ReplayPage />} />
            <Route path="/auth" element={<AuthPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </SettingsProvider>
  );
}

export default App;
