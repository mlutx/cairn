import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription
} from "@/components/ui/dialog";
import { fetchConnectedRepos, refreshReposCache } from "@/lib/api";
import { Loader2, AlertCircle, Github, Info, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "@/components/ui/use-toast";

interface Repository {
  owner: string;
  repo: string;
  installation_id?: number;
  rules?: string[];
}

interface RepoResponse {
  repos: Repository[];
  general_rules: string[];
}

interface RepoModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RepoModal({ open, onOpenChange }: RepoModalProps) {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [generalRules, setGeneralRules] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRepos = () => {
    setLoading(true);
    setError(null);
    fetchConnectedRepos()
      .then((data: RepoResponse) => {
        setRepos(data.repos);
        setGeneralRules(data.general_rules || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching repos:", err);
        setError("Failed to load repositories. Make sure the FastAPI server is running at http://localhost:8000.");
        setLoading(false);
      });
  };

  const handleRefreshCache = async () => {
    if (refreshing) return;

    setRefreshing(true);
    try {
      await refreshReposCache();
      toast({
        title: "Cache refreshed",
        description: "Repository and settings cache has been refreshed.",
      });
      // Fetch the updated data
      await fetchRepos();
    } catch (err) {
      console.error("Error refreshing cache:", err);
      toast({
        title: "Refresh failed",
        description: "Failed to refresh cache. Please try again.",
        variant: "destructive",
      });
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchRepos();
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Github className="h-5 w-5" />
            <DialogTitle>Connected Repositories</DialogTitle>
          </div>
          <div className="flex items-center justify-between gap-2 mt-1">
            <DialogDescription className="flex-1">
              To edit repositories, edit repos.json. To add rules, go to .cairn/settings.json.
            </DialogDescription>
            <Button
              variant="outline"
              size="icon"
              onClick={handleRefreshCache}
              disabled={refreshing || loading}
              className="h-7 w-7 flex-shrink-0"
              title="Refresh cache"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </DialogHeader>
        <div className="py-2">
          {loading ? (
            <div className="flex justify-center items-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center py-4 text-destructive">
              <AlertCircle className="h-8 w-8 mb-2" />
              <p className="text-center mb-4">{error}</p>
              <Button onClick={fetchRepos} variant="outline" size="sm">
                Retry
              </Button>
            </div>
          ) : (
            <ScrollArea className="max-h-[400px] pr-3">
              {/* Repositories Section */}
              {repos.length === 0 ? (
                <div className="text-center py-4 text-muted-foreground text-sm">
                  No repositories connected.
                </div>
              ) : (
                <div className="space-y-3">
                  {repos.map((repo) => (
                    <div
                      key={`${repo.owner}/${repo.repo}`}
                      className="rounded-md border border-border p-3 hover:bg-accent/30 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <a
                          href={`https://github.com/${repo.owner}/${repo.repo}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium hover:underline"
                        >
                          {repo.owner}/{repo.repo}
                        </a>
                        {repo.installation_id && (
                          <Badge variant="outline" className="text-xs font-normal">
                            Install ID: {repo.installation_id}
                          </Badge>
                        )}
                      </div>

                      {/* Repository Rules */}
                      {repo.rules && repo.rules.length > 0 && (
                        <div className="mt-2">
                          <Separator className="my-2" />
                          <h4 className="text-xs font-medium mb-1.5 text-muted-foreground">Repository Rules:</h4>
                          <ul className="text-xs space-y-1 list-disc pl-4">
                            {repo.rules.map((rule, index) => (
                              <li key={index}>{rule}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* General Rules Section - Moved below repositories */}
              {generalRules.length > 0 && (
                <div className="mt-4 pt-2">
                  <Separator className="mb-4" />
                  <h3 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                    <Info className="h-4 w-4" />
                    General Rules
                  </h3>
                  <div className="bg-muted/50 rounded-md p-2.5">
                    <ul className="text-xs space-y-1 list-disc pl-4">
                      {generalRules.map((rule, index) => (
                        <li key={index}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </ScrollArea>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
