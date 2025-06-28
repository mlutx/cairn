import { Task } from "@/types";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { format } from "date-fns";
import { ExternalLink, Github, Calendar, User, Settings, Server, Code, GitBranch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

// Import logo images
import openaiLogo from "@/assets/openai.png";
import anthropicLogo from "@/assets/anthropic.png";
import geminiLogo from "@/assets/gemini.png";
import fullstackIcon from "@/assets/fullstack-icon.png";
import pmIcon from "@/assets/pm-icon.png";
import sweIcon from "@/assets/swe-icon.png";

interface TaskDetailsModalProps {
  task: Task | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const customStyles = `
  /* Linear input and textarea styles */
  .linear-input {
    border: none;
    outline: none;
    box-shadow: none;
    padding: 0;
    height: auto;
    background: transparent;
    font-size: 1.125rem;
    font-weight: 500;
  }

  .linear-input:focus {
    outline: none;
    box-shadow: none;
    ring: none;
  }

  .linear-textarea {
    border: none;
    outline: none;
    box-shadow: none;
    padding: 0;
    background: transparent;
    resize: none;
    min-height: 80px;
  }

  .linear-textarea:focus {
    outline: none;
    box-shadow: none;
    ring: none;
  }

  /* Menu item styles */
  .linear-menu {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 5px 8px;
    border-radius: 4px;
    border: none;
    background: transparent;
    font-size: 14px;
    color: #888;
    height: 28px;
  }

  .linear-menu:hover {
    background-color: rgba(0, 0, 0, 0.05);
  }

  /* Status color dots */
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
  }

  .queued-dot { background-color: #4673fa; }
  .running-dot { background-color: #f2c94c; }
  .done-dot { background-color: #27ae60; }
  .failed-dot { background-color: #eb5757; }
  .waiting-dot { background-color: #9b59b6; }

  /* Detail section styles */
  .detail-section {
    display: flex;
    flex-col;
    gap: 2px;
    margin-bottom: 8px;
  }

  .detail-content {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px;
    border-radius: 4px;
    background: transparent;
    font-size: 14px;
    color: #333;
    min-height: 28px;
  }

  .dark .detail-content {
    color: #e5e5e5;
  }

  /* Additional fields container */
  .additional-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding-top: 3px;
    margin-top: 2px;
    margin-bottom: -8px;
  }

  /* Additional field style */
  .additional-field {
    flex: 1 1 calc(33.333% - 6px);
    min-width: 100px;
  }
`;

export default function TaskDetailsModal({ task, open, onOpenChange }: TaskDetailsModalProps) {
  if (!task) return null;

  const getModelProviderLogo = (provider: string): string => {
    switch (provider?.toLowerCase()) {
      case "openai":
        return openaiLogo;
      case "anthropic":
        return anthropicLogo;
      case "google":
      case "gemini":
        return geminiLogo;
      default:
        return "";
    }
  };

  const getAgentTypeIcon = (type: string): string => {
    switch (type) {
      case "SWE":
        return sweIcon;
      case "PM":
        return pmIcon;
      case "Fullstack":
        return fullstackIcon;
      default:
        return "";
    }
  };

  const getStatusDot = (status: string) => {
    switch (status) {
      case "Queued":
        return "queued-dot";
      case "Running":
        return "running-dot";
      case "Done":
        return "done-dot";
      case "Failed":
        return "failed-dot";
      case "Waiting for Input":
        return "waiting-dot";
      default:
        return "queued-dot";
    }
  };

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), "MMM d, yyyy 'at' h:mm a");
    } catch {
      return "Invalid date";
    }
  };

        const renderSWEDetails = () => {
    const [showSummary, setShowSummary] = useState(false);
    const [showFiles, setShowFiles] = useState(false);
    const [showVerification, setShowVerification] = useState(false);
    const [showAdditionalNotes, setShowAdditionalNotes] = useState(false);

    return (
      <>
        {/* Branch URL - Prominently displayed */}
        {(task as any).agent_output?.branch_url && (
          <div className="mt-2">
            <Button
              onClick={() => window.open((task as any).agent_output.branch_url, '_blank')}
              className="gap-2 h-8 w-full text-white"
              style={{ backgroundColor: '#5d70d5' }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#4a5bb8'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#5d70d5'}
            >
              <GitBranch className="h-4 w-4" />
              View Branch
            </Button>
          </div>
        )}

        {/* Task Details Summary */}
        {/* <div className="mt-3 mb-2">
          <div className="text-xs text-muted-foreground">
            Showing status, agent type, and repositories above. Agent output details below:
          </div>
        </div> */}

        {/* Collapsible Sections in 2x2 Grid */}
        <div className="grid grid-cols-2 gap-3">
          {/* Summary of Changes */}
          {(task as any).agent_output?.summary_of_changes && (
            <div className="space-y-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSummary(!showSummary)}
                className="h-6 p-1 text-xs text-muted-foreground font-medium hover:text-foreground w-full justify-start"
              >
                {showSummary ? '▼' : '▶'} Summary of Changes
              </Button>
              {showSummary && (
                <div className="text-xs p-2 border rounded">
                  {(task as any).agent_output.summary_of_changes}
                </div>
              )}
            </div>
          )}

          {/* Files Modified */}
          {(task as any).agent_output?.files_modified && (task as any).agent_output.files_modified.length > 0 && (
            <div className="space-y-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowFiles(!showFiles)}
                className="h-6 p-1 text-xs text-muted-foreground font-medium hover:text-foreground w-full justify-start"
              >
                {showFiles ? '▼' : '▶'} Files Modified ({(task as any).agent_output.files_modified.length})
              </Button>
              {showFiles && (
                <div className="space-y-1">
                  {(task as any).agent_output.files_modified.map((file: string, idx: number) => (
                    <div key={idx} className="text-xs p-1 border rounded font-mono">
                      {file}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Verification Status */}
          {(task as any).agent_output?.verification_status && (
            <div className="space-y-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowVerification(!showVerification)}
                className="h-6 p-1 text-xs text-muted-foreground font-medium hover:text-foreground w-full justify-start"
              >
                {showVerification ? '▼' : '▶'} Verification Status
              </Button>
              {showVerification && (
                <div className="text-xs p-2 border rounded">
                  {(task as any).agent_output.verification_status}
                </div>
              )}
            </div>
          )}

          {/* Additional Notes */}
          {(task as any).agent_output?.additional_notes && (
            <div className="space-y-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAdditionalNotes(!showAdditionalNotes)}
                className="h-6 p-1 text-xs text-muted-foreground font-medium hover:text-foreground w-full justify-start"
              >
                {showAdditionalNotes ? '▼' : '▶'} Additional Notes
              </Button>
              {showAdditionalNotes && (
                <div className="text-xs p-2 border rounded">
                  {(task as any).agent_output.additional_notes}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Legacy fields - Keep for backward compatibility */}
        {/* Branch Information - if available in legacy format */}
        {(task as any).agent_output?.branch && !(task as any).agent_output?.branch_url && (
          <div className="detail-section">
            <div className="detail-content linear-menu">
              <GitBranch className="h-3.5 w-3.5 opacity-70" />
              <span className="font-mono text-sm">{(task as any).agent_output.branch}</span>
            </div>
          </div>
        )}

        {/* Pull Request Link - if available */}
        {(task as any).agent_output?.pr_url && (
          <div className="mt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open((task as any).agent_output.pr_url, '_blank')}
              className="gap-2 h-7"
            >
              <ExternalLink className="h-3 w-3" />
              View PR
            </Button>
          </div>
        )}

        {/* Issues Encountered - if available */}
        {(task as any).agent_output?.issues_encountered && (task as any).agent_output.issues_encountered.length > 0 && (
          <div className="mt-3 space-y-2">
            <div className="text-xs text-muted-foreground font-medium">Issues Encountered:</div>
            {(task as any).agent_output.issues_encountered.map((issue: string, idx: number) => (
              <div key={idx} className="text-xs p-2 bg-orange-50 dark:bg-orange-950/20 rounded border-l-2 border-orange-400">
                {issue}
              </div>
            ))}
          </div>
        )}

        {/* Recommendations - if available */}
        {(task as any).agent_output?.recommendations && (task as any).agent_output.recommendations.length > 0 && (
          <div className="mt-3 space-y-2">
            <div className="text-xs text-muted-foreground font-medium">Recommendations:</div>
            {(task as any).agent_output.recommendations.map((rec: string, idx: number) => (
              <div key={idx} className="text-xs p-2 bg-blue-50 dark:bg-blue-950/20 rounded border-l-2 border-blue-400">
                {rec}
              </div>
            ))}
          </div>
        )}
      </>
    );
  };

  const renderPMDetails = () => (
    <>
      {/* Parent Task Information - if available */}
      {task.parent_fullstack_id && (
        <div className="detail-section">
          <div className="detail-content linear-menu">
            <User className="h-3.5 w-3.5 opacity-70" />
            <span className="text-sm">Parent: {task.parent_fullstack_id}</span>
          </div>
        </div>
      )}

      {/* Subtasks - if available */}
      {task.sibling_subtask_ids && task.sibling_subtask_ids.length > 0 && (
        <div className="detail-section">
          <div className="detail-content linear-menu">
            <Settings className="h-3.5 w-3.5 opacity-70" />
            <span className="text-sm">
              {task.sibling_subtask_ids.length} subtask{task.sibling_subtask_ids.length > 1 ? 's' : ''}
            </span>
          </div>
        </div>
      )}
    </>
  );

  const renderFullstackDetails = () => (
    <>
      {/* Subtasks Generated - if available */}
      {(task as any).agent_output?.list_of_subtasks && (
        <div className="detail-section">
          <div className="detail-content linear-menu">
            <Settings className="h-3.5 w-3.5 opacity-70" />
            <span className="text-sm">
              {(task as any).agent_output.list_of_subtasks.length} subtask{(task as any).agent_output.list_of_subtasks.length > 1 ? 's' : ''} generated
            </span>
          </div>
        </div>
      )}

      {/* Child Tasks - if available */}
      {task.sibling_subtask_ids && task.sibling_subtask_ids.length > 0 && (
        <div className="detail-section">
          <div className="detail-content linear-menu">
            <Settings className="h-3.5 w-3.5 opacity-70" />
            <span className="text-sm">
              {task.sibling_subtask_ids.length} child task{task.sibling_subtask_ids.length > 1 ? 's' : ''}
            </span>
          </div>
        </div>
      )}
    </>
  );

  const renderAgentSpecificDetails = () => {
    switch (task.agent_type) {
      case "SWE":
        return renderSWEDetails();
      case "PM":
        return renderPMDetails();
      case "Fullstack":
        return renderFullstackDetails();
      default:
        return null;
    }
  };

    return (
    <>
      <style dangerouslySetInnerHTML={{ __html: customStyles }} />
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[550px] p-0 gap-0 overflow-hidden border rounded-lg shadow-lg">
          <div className="p-3 space-y-4">
            {/* Title (displayed like input field) */}
            <div className="linear-input text-lg font-medium">
              {task.title}
            </div>

            {/* Description (displayed like textarea) */}
            {task.description && (
                                                        <div
                style={{
                  border: '1px solid rgba(93, 112, 213, 0.3)',
                  padding: '8px 12px',
                  fontSize: '0.875rem',
                  color: 'var(--muted-foreground)',
                  maxHeight: '6rem',
                  overflowY: 'auto',
                  borderRadius: '0.25rem',
                  background: 'transparent',
                  resize: 'none',
                  minHeight: '80px'
                }}
              >
                {task.description}
              </div>
            )}

            <div className="flex flex-col space-y-1">
              {/* Status and Agent Type - Side by side */}
              <div className="flex gap-2">
                {/* Status */}
                <div className="flex-1">
                  <div className="detail-content linear-menu">
                    <span className={`status-dot ${getStatusDot(task.status)}`}></span>
                    <span>{task.status}</span>
                  </div>
                </div>

                {/* Agent Type */}
                <div className="flex-1">
                  <div className="detail-content linear-menu">
                    {task.agent_type && getAgentTypeIcon(task.agent_type) && (
                      <img
                        src={getAgentTypeIcon(task.agent_type)}
                        alt={`${task.agent_type} icon`}
                        className="h-3.5 w-3.5 object-contain"
                      />
                    )}
                    <span>{task.agent_type || 'Unknown'}</span>
                  </div>
                </div>
              </div>

              {/* Model Provider and Model - Side by side */}
              {(task.model_provider || task.model_name) && (
                <div className="flex gap-2">
                  {/* Model Provider */}
                  {task.model_provider && (
                    <div className="flex-1">
                      <div className="detail-content linear-menu">
                        {getModelProviderLogo(task.model_provider) && (
                          <img
                            src={getModelProviderLogo(task.model_provider)}
                            alt={`${task.model_provider} logo`}
                            className="h-3.5 w-3.5 object-contain"
                          />
                        )}
                        <span>{task.model_provider}</span>
                      </div>
                    </div>
                  )}

                  {/* Model Name */}
                  {task.model_name && (
                    <div className="flex-1">
                      <div className="detail-content linear-menu">
                        <Code className="h-3.5 w-3.5 opacity-70" />
                        <span>{task.model_name}</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Repository Information */}
            {task.repos && task.repos.length > 0 && (
              <div className="mt-2 pl-[5px]">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <Github className="h-3.5 w-3.5 opacity-70" />
                    <span className="text-sm font-medium">Repos:</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {task.repos.map((repo, idx) => (
                      <div
                        key={idx}
                        className="px-2 py-1 bg-gray-50 dark:bg-gray-900/50 rounded text-xs border-gray-200 dark:border-gray-700 border"
                      >
                        {repo}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Agent-specific details */}
            {renderAgentSpecificDetails()}

            {/* Dates and additional information */}
            <div className="space-y-2 mt-4 pt-2 border-t border-border/30">
              <div className="flex items-center justify-between gap-4 text-xs text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Calendar className="h-3 w-3" />
                  <span>Created {formatDate(task.created_at)}</span>
                  {/* {task.created_by && <span>by {task.created_by}</span>} */}
                </div>

                {task.updated_at && task.updated_at !== task.created_at && (
                  <div className="flex items-center gap-2">
                    <Calendar className="h-3 w-3" />
                    <span>Updated {formatDate(task.updated_at)}</span>
                  </div>
                )}
              </div>

              {task.due_date && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  <span>Due {formatDate(task.due_date)}</span>
                </div>
              )}
            </div>

            {/* Tags */}
            {task.tags && task.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {task.tags.map((tag, idx) => (
                  <Badge key={idx} variant="secondary" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}

            {/* External Link */}
            {task.link && (
              <div className="mt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(task.link, '_blank')}
                  className="gap-2 h-7"
                >
                  <ExternalLink className="h-3 w-3" />
                  Open Link
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
