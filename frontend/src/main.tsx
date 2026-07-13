import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { AuthProvider } from "./context/AuthProvider";
import { AttendanceAccessProvider } from "./context/AttendanceAccessProvider";
import { loadAppearanceSettings } from "./lib/theme";
import "./index.css";

const THEME_STORAGE_KEY = "theme";
const applyInitialTheme = () => {
  if (typeof window === "undefined") return;
  const persisted = localStorage.getItem(THEME_STORAGE_KEY);
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = persisted === "dark" || persisted === "light" ? persisted : (prefersDark ? "dark" : "light");
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
};

applyInitialTheme();
void loadAppearanceSettings();

createRoot(document.getElementById("root")!).render(
  <AuthProvider>
    <AttendanceAccessProvider>
      <App />
    </AttendanceAccessProvider>
  </AuthProvider>
);
