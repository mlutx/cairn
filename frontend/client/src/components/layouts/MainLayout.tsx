import { ReactNode, useState, useEffect } from "react";
import Header from "./Header";
import { ThemeProvider } from "@/components/ui/theme-provider";
import "@/styles/linear-ui.css";

interface MainLayoutProps {
  children: ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  const [themeClass, setThemeClass] = useState("theme-dark");

  // Detect system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const updateTheme = (e: MediaQueryListEvent | MediaQueryList) => {
      setThemeClass(e.matches ? 'theme-dark' : 'theme-light');
    };

    updateTheme(mediaQuery);
    mediaQuery.addEventListener('change', updateTheme);

    return () => {
      mediaQuery.removeEventListener('change', updateTheme);
    };
  }, []);

  return (
    <ThemeProvider defaultTheme="system" storageKey="cairn-theme">
      <div className={`min-h-screen flex flex-col bg-background text-foreground linear-tabs ${themeClass}`}>
        <div className="flex-1 flex flex-col overflow-x-hidden">
          <Header />
          <main className="flex-1">
            {children}
          </main>
        </div>
      </div>
    </ThemeProvider>
  );
}
