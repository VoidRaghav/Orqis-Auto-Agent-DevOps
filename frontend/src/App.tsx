import { Route, Routes } from "react-router-dom";
import Home from "@/pages/Home";
import DashboardPage from "@/pages/DashboardPage";
import SettingsPage from "@/pages/SettingsPage";
import LoginPage from "@/pages/LoginPage";
import InvitePage from "@/pages/InvitePage";
import AuthGuard from "@/components/AuthGuard";
import MultiTenantConfigGuard from "@/components/MultiTenantConfigGuard";

export default function App() {
  return (
    <>
      <MultiTenantConfigGuard />
      <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/invite/:token" element={<InvitePage />} />
      <Route element={<AuthGuard />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
    </>
  );
}
