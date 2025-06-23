interface HeaderProps {}

export default function Header({}: HeaderProps) {
  // We're moving the repo functionality to the dashboard
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/60 h-10 md:hidden">
      <div className="flex h-full items-center px-2">
        {/* Header content moved to dashboard */}
      </div>
    </header>
  );
}
