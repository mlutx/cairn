import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/AuthContext";
import { TaskProvider } from "@/contexts/TaskContext";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/toaster";
import { queryClient } from "./lib/queryClient";
import MainLayout from "@/components/layouts/MainLayout";
import { ThemeProvider } from "@/contexts/ThemeContext";

// Pages
import Dashboard from "@/pages/dashboard";
import NotFound from "@/pages/not-found";

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TaskProvider>
          <TooltipProvider>
            <ThemeProvider>
            <Router>
                    <MainLayout>
                    <Routes>
                      <Route path="/" element={<Dashboard />} />
                      <Route path="*" element={<NotFound />} />
                    </Routes>
                  </MainLayout>
                    <Toaster />
              </Router>
            </ThemeProvider>
        </TooltipProvider>
        </TaskProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
