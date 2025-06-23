import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PlusIcon, Filter, Github } from "lucide-react";
import KanbanBoard from "@/components/task/KanbanBoard";
import ListView from "@/components/task/ListView";
import TaskForm from "@/components/task/TaskForm";
import { useTasks } from "@/contexts/TaskContext";
import "@/styles/linear-ui.css";
import { useSearchParams } from "react-router-dom";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { RepoModal } from "@/components/repos/RepoModal";

export default function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialView = searchParams.get('view') || "kanban";
  const [activeView, setActiveView] = useState<string>(initialView);
  const [isTaskFormOpen, setIsTaskFormOpen] = useState(false);
  const [repoModalOpen, setRepoModalOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [contentHeight, setContentHeight] = useState<number>(0);
  const { isLoading } = useTasks();

  // Calculate available height for content
  useEffect(() => {
    const calculateHeight = () => {
      if (containerRef.current) {
        const containerTop = containerRef.current.getBoundingClientRect().top;
        const windowHeight = window.innerHeight;
        setContentHeight(windowHeight - containerTop - 24); // 24px buffer
      }
    };
    calculateHeight();
    window.addEventListener('resize', calculateHeight);
    return () => window.removeEventListener('resize', calculateHeight);
  }, []);

    // Add keyboard shortcut for Cmd+K to toggle task form
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsTaskFormOpen(prevState => !prevState); // Toggle the form state
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  // Update URL when tab changes
  useEffect(() => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set('view', activeView);
    setSearchParams(newParams);
  }, [activeView, setSearchParams]);

  const handleViewChange = (value: string) => {
    setActiveView(value);
  };

  return (
    <div className="mt-4 px-4 md:px-6 flex flex-col">
      <Tabs
        defaultValue="kanban"
        value={activeView}
        onValueChange={handleViewChange}
        className="w-full"
      >
        <div className="flex items-center justify-between gap-4 mb-3">
          <TabsList>
            <TabsTrigger value="kanban" className="flex items-center text-xs">
              <svg xmlns="http://www.w3.org/2000/svg" className="mr-1.5 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              <span>Kanban Board</span>
            </TabsTrigger>
            <TabsTrigger value="list" className="flex items-center text-xs">
              <svg xmlns="http://www.w3.org/2000/svg" className="mr-1.5 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
              <span>List View</span>
            </TabsTrigger>
          </TabsList>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setRepoModalOpen(true)}
              className="h-9 w-9"
              title="View connected repositories"
            >
              <Github className="h-5 w-5" />
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="linear-button"
              onClick={() => {}}
            >
              <Filter className="linear-button-icon mr-1" />
              <span>Filter</span>
            </Button>
            <Button
              size="sm"
              className="linear-button"
              onClick={() => setIsTaskFormOpen(prev => !prev)}
            >
              <PlusIcon className="linear-button-icon mr-1" />
              <span>Add Task <span className="ml-1 opacity-70 text-xs">⌘+K</span></span>
            </Button>
          </div>
        </div>
        <div ref={containerRef} className="flex-grow" style={{ height: contentHeight ? `${contentHeight}px` : 'auto' }}>
          <TabsContent value="kanban" className="h-full mt-0 p-0">
            <KanbanBoard project="" />
          </TabsContent>
          <TabsContent value="list" className="h-full mt-0 p-0">
            <ListView project="" />
          </TabsContent>
        </div>
      </Tabs>
      {/* Task Add Form Dialog */}
      <TaskForm
        open={isTaskFormOpen}
        onOpenChange={setIsTaskFormOpen}
        mode="create"
      />
      {/* Repository Modal */}
      <RepoModal open={repoModalOpen} onOpenChange={setRepoModalOpen} />
    </div>
  );
}
