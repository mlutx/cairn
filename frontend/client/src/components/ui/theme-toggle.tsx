import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/ui/theme-provider";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <div
      className="relative flex h-8 w-16 cursor-pointer items-center justify-between rounded-full border border-border bg-muted p-1"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      role="button"
      tabIndex={0}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          setTheme(isDark ? "light" : "dark");
        }
      }}
    >
      <div className={`absolute left-1 h-6 w-7 rounded-full bg-primary transition-transform duration-200 ${
        isDark ? "translate-x-7" : "translate-x-0"
      }`} />

      <div className="z-10 flex h-6 w-6 items-center justify-center rounded-full">
        <Sun className={`h-4 w-4 ${!isDark ? "text-primary-foreground" : "text-foreground"}`} />
      </div>

      <div className="z-10 flex h-6 w-6 items-center justify-center rounded-full">
        <Moon className={`h-4 w-4 ${isDark ? "text-primary-foreground" : "text-foreground"}`} />
      </div>
    </div>
  );
}
