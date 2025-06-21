import { Button } from "@/components/ui/button";

interface HeaderProps {}

export default function Header({}: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/60 h-10 md:hidden">
      <div className="flex h-full items-center px-2">
        {/* Sidebar toggle button removed */}
      </div>
    </header>
  );
}
