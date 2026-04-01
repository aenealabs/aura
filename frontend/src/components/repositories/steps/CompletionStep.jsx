/**
 * Project Aura - Completion Step
 *
 * Step 5 of the Repository Onboarding Wizard.
 * Shows ingestion progress and results.
 *
 * Part of ADR-043: Repository Onboarding Wizard
 */

import { useRepositories } from '../../../context/RepositoryContext';
import { IngestionStatus } from '../../../services/repositoryApi';

const CompletionStep = ({ onClose, onAddMore }) => {
  const {
    ingestionJobs,
    isWizardLoading: _isWizardLoading,
    wizardError,
    cancelIngestionJob,
    resetWizard,
  } = useRepositories();

  // Calculate overall progress
  const completedJobs = ingestionJobs.filter(
    (j) => j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled'
  );
  const isComplete = completedJobs.length === ingestionJobs.length && ingestionJobs.length > 0;
  const successCount = ingestionJobs.filter((j) => j.status === 'completed').length;
  const failedCount = ingestionJobs.filter((j) => j.status === 'failed').length;

  const statusLabels = {
    [IngestionStatus.QUEUED]: 'Queued',
    [IngestionStatus.CLONING]: 'Cloning Repository',
    [IngestionStatus.PARSING]: 'Parsing Code',
    [IngestionStatus.INDEXING_GRAPH]: 'Building Graph',
    [IngestionStatus.INDEXING_VECTORS]: 'Generating Embeddings',
    [IngestionStatus.COMPLETED]: 'Completed',
    [IngestionStatus.FAILED]: 'Failed',
    [IngestionStatus.CANCELLED]: 'Cancelled',
  };

  const statusColors = {
    [IngestionStatus.QUEUED]: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400',
    [IngestionStatus.CLONING]: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    [IngestionStatus.PARSING]: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    [IngestionStatus.INDEXING_GRAPH]: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    [IngestionStatus.INDEXING_VECTORS]: 'bg-aura-100 text-aura-600 dark:bg-aura-900/30 dark:text-aura-400',
    [IngestionStatus.COMPLETED]: 'bg-olive-100 text-olive-600 dark:bg-olive-900/30 dark:text-olive-400',
    [IngestionStatus.FAILED]: 'bg-critical-100 text-critical-600 dark:bg-critical-900/30 dark:text-critical-400',
    [IngestionStatus.CANCELLED]: 'bg-warning-100 text-warning-600 dark:bg-warning-900/30 dark:text-warning-400',
  };

  const handleClose = () => {
    resetWizard();
    if (onClose) onClose();
  };

  const handleAddMore = () => {
    resetWizard();
    if (onAddMore) onAddMore();
  };

  const isInProgress = (status) => {
    return ['queued', 'cloning', 'parsing', 'indexing_graph', 'indexing_vectors'].includes(status);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
          {isComplete ? 'Ingestion Complete' : 'Ingesting Repositories'}
        </h2>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
          {isComplete
            ? `Processed ${ingestionJobs.length} repository/repositories.`
            : 'Your repositories are being analyzed. This may take a few minutes.'}
        </p>
      </div>

      {wizardError && (
        <div className="p-4 bg-critical-50 dark:bg-critical-900/20 border border-critical-200 dark:border-critical-800 rounded-lg">
          <p className="text-sm text-critical-700 dark:text-critical-400">{wizardError}</p>
        </div>
      )}

      {/* Overall Progress */}
      {!isComplete && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-surface-600 dark:text-surface-400">
              Overall Progress
            </span>
            <span className="text-surface-900 dark:text-surface-100">
              {completedJobs.length} / {ingestionJobs.length}
            </span>
          </div>
          <div className="w-full bg-surface-200 dark:bg-surface-700 rounded-full h-2">
            <div
              className="bg-aura-600 h-2 rounded-full transition-all duration-500"
              style={{
                width: `${(completedJobs.length / Math.max(ingestionJobs.length, 1)) * 100}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Summary on Completion */}
      {isComplete && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 bg-olive-50 dark:bg-olive-900/20 rounded-lg text-center">
            <p className="text-2xl font-bold text-olive-600 dark:text-olive-400">
              {successCount}
            </p>
            <p className="text-sm text-olive-700 dark:text-olive-300">Successful</p>
          </div>
          <div className="p-4 bg-critical-50 dark:bg-critical-900/20 rounded-lg text-center">
            <p className="text-2xl font-bold text-critical-600 dark:text-critical-400">
              {failedCount}
            </p>
            <p className="text-sm text-critical-700 dark:text-critical-300">Failed</p>
          </div>
          <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-lg text-center">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              {ingestionJobs.reduce((sum, j) => sum + (j.entities_indexed || 0), 0)}
            </p>
            <p className="text-sm text-surface-600 dark:text-surface-400">Entities</p>
          </div>
        </div>
      )}

      {/* Job List */}
      <div className="space-y-3 max-h-64 overflow-y-auto">
        {ingestionJobs.map((job) => (
          <div
            key={job.job_id}
            className="p-4 border border-surface-200 dark:border-surface-700 rounded-lg"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                  {job.repository_name}
                </p>
                <div className="mt-1 flex items-center gap-2">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      statusColors[job.status] || statusColors[IngestionStatus.QUEUED]
                    }`}
                  >
                    {statusLabels[job.status] || job.status}
                  </span>
                  {job.stage && isInProgress(job.status) && (
                    <span className="text-xs text-surface-500">
                      {job.stage}
                    </span>
                  )}
                </div>
              </div>
              {isInProgress(job.status) && (
                <button
                  onClick={() => cancelIngestionJob(job.job_id)}
                  className="text-xs text-critical-600 hover:text-critical-700 dark:text-critical-400"
                >
                  Cancel
                </button>
              )}
            </div>

            {/* Progress Bar */}
            {isInProgress(job.status) && (
              <div className="mt-3 space-y-1">
                <div className="w-full bg-surface-200 dark:bg-surface-700 rounded-full h-1.5">
                  <div
                    className="bg-aura-600 h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${job.progress || 0}%` }}
                  />
                </div>
                <p className="text-xs text-surface-500">
                  {job.files_processed || 0} files processed
                </p>
              </div>
            )}

            {/* Stats on Completion */}
            {job.status === 'completed' && (
              <div className="mt-2 flex gap-4 text-xs text-surface-500">
                <span>{job.files_processed || 0} files</span>
                <span>{job.entities_indexed || 0} entities</span>
                <span>{job.embeddings_generated || 0} embeddings</span>
              </div>
            )}

            {/* Error Message */}
            {job.status === 'failed' && job.error_message && (
              <div className="mt-2 p-2 bg-critical-50 dark:bg-critical-900/20 rounded">
                <p className="text-xs text-critical-700 dark:text-critical-400">
                  {job.error_message}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex justify-between pt-4 border-t border-surface-200 dark:border-surface-700">
        {isComplete ? (
          <>
            <button
              onClick={handleAddMore}
              className="px-4 py-2 border border-surface-300 dark:border-surface-600 rounded-lg text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-800"
            >
              Add More Repositories
            </button>
            <button
              onClick={handleClose}
              className="px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700"
            >
              View Dashboard
            </button>
          </>
        ) : (
          <>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Please wait while ingestion completes...
            </p>
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm text-surface-600 hover:text-surface-800 dark:text-surface-400 dark:hover:text-surface-200"
            >
              Run in Background
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default CompletionStep;
