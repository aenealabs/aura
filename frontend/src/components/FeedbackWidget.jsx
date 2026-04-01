/**
 * FeedbackWidget Component
 *
 * In-app feedback collection widget for beta users.
 * Provides a floating button that opens a feedback modal.
 *
 * Features:
 * - Multiple feedback types (general, bug, feature request, etc.)
 * - NPS survey integration
 * - Screenshot capture (optional)
 * - Automatic page context capture
 */

import { useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

// Feedback types with icons and descriptions
const FEEDBACK_TYPES = [
  {
    type: 'general',
    label: 'General Feedback',
    icon: '💬',
    description: 'Share your thoughts about the platform',
  },
  {
    type: 'bug_report',
    label: 'Report a Bug',
    icon: '🐛',
    description: 'Something not working as expected?',
  },
  {
    type: 'feature_request',
    label: 'Feature Request',
    icon: '💡',
    description: 'Suggest a new feature or improvement',
  },
  {
    type: 'usability',
    label: 'Usability Issue',
    icon: '🎯',
    description: 'Difficulty using a feature?',
  },
  {
    type: 'documentation',
    label: 'Documentation',
    icon: '📚',
    description: 'Missing or unclear documentation',
  },
  {
    type: 'performance',
    label: 'Performance',
    icon: '⚡',
    description: 'Slow or unresponsive features',
  },
];

// NPS score labels
const NPS_LABELS = {
  0: 'Not at all likely',
  5: 'Neutral',
  10: 'Extremely likely',
};

const FeedbackWidget = ({ position = 'bottom-right' }) => {
  const { user: _user, isAuthenticated } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [showNPS, setShowNPS] = useState(false);
  const [feedbackType, setFeedbackType] = useState(null);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    tags: [],
  });
  const [npsScore, setNpsScore] = useState(null);
  const [npsComment, setNpsComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [error, setError] = useState(null);

  // Position classes
  const positionClasses = {
    'bottom-right': 'bottom-6 right-6',
    'bottom-left': 'bottom-6 left-6',
    'top-right': 'top-6 right-6',
    'top-left': 'top-6 left-6',
  };

  const handleOpen = useCallback(() => {
    setIsOpen(true);
    setFeedbackType(null);
    setFormData({ title: '', description: '', tags: [] });
    setSubmitSuccess(false);
    setError(null);
  }, []);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    setShowNPS(false);
    setFeedbackType(null);
    setNpsScore(null);
    setNpsComment('');
  }, []);

  const handleSelectType = useCallback((type) => {
    setFeedbackType(type);
  }, []);

  const handleInputChange = useCallback((e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleTagToggle = useCallback((tag) => {
    setFormData((prev) => ({
      ...prev,
      tags: prev.tags.includes(tag)
        ? prev.tags.filter((t) => t !== tag)
        : [...prev.tags, tag],
    }));
  }, []);

  const handleSubmitFeedback = useCallback(async () => {
    if (!feedbackType || !formData.title || !formData.description) {
      setError('Please fill in all required fields');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          feedback_type: feedbackType,
          title: formData.title,
          description: formData.description,
          tags: formData.tags,
          page_url: window.location.href,
          metadata: {
            viewport: `${window.innerWidth}x${window.innerHeight}`,
            timestamp: new Date().toISOString(),
          },
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }

      setSubmitSuccess(true);
      setTimeout(() => {
        handleClose();
      }, 2000);
    } catch (err) {
      setError(err.message || 'Failed to submit feedback');
    } finally {
      setIsSubmitting(false);
    }
  }, [feedbackType, formData, handleClose]);

  const handleSubmitNPS = useCallback(async () => {
    if (npsScore === null) {
      setError('Please select a score');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/feedback/nps', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          score: npsScore,
          comment: npsComment || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit survey');
      }

      setSubmitSuccess(true);
      setTimeout(() => {
        handleClose();
      }, 2000);
    } catch (err) {
      setError(err.message || 'Failed to submit survey');
    } finally {
      setIsSubmitting(false);
    }
  }, [npsScore, npsComment, handleClose]);

  // Don't render for unauthenticated users
  if (!isAuthenticated) {
    return null;
  }

  // Common tags for feedback
  const commonTags = ['dashboard', 'agents', 'approvals', 'security', 'performance', 'ui'];

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={handleOpen}
        className={`fixed ${positionClasses[position]} z-50 bg-aura-600 hover:bg-aura-700 text-white rounded-full p-4 shadow-lg transition-all duration-200 hover:scale-110 focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2 dark:ring-offset-surface-900`}
        aria-label="Open feedback"
        title="Send Feedback"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </button>

      {/* Modal Overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-end justify-center px-4 pt-4 pb-20 text-center sm:block sm:p-0">
            {/* Background overlay */}
            <div
              className="fixed inset-0 bg-surface-900/75 dark:bg-black/75 transition-opacity"
              onClick={handleClose}
            />

            {/* Modal panel */}
            <div className="relative inline-block transform overflow-hidden rounded-lg bg-white dark:bg-surface-800 text-left align-bottom shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:align-middle">
              {/* Header */}
              <div className="bg-aura-600 dark:bg-aura-700 px-6 py-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-white">
                    {showNPS
                      ? 'How likely are you to recommend us?'
                      : feedbackType
                      ? FEEDBACK_TYPES.find((t) => t.type === feedbackType)?.label
                      : 'Send Feedback'}
                  </h3>
                  <button
                    onClick={handleClose}
                    className="text-white hover:text-surface-200"
                  >
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="px-6 py-4">
                {submitSuccess ? (
                  <div className="text-center py-8">
                    <div className="text-5xl mb-4">🎉</div>
                    <h4 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">
                      Thank you for your feedback!
                    </h4>
                    <p className="text-surface-600 dark:text-surface-400">
                      Your input helps us improve the platform.
                    </p>
                  </div>
                ) : showNPS ? (
                  /* NPS Survey */
                  <div>
                    <p className="text-surface-600 dark:text-surface-400 mb-6 text-center">
                      On a scale of 0-10, how likely are you to recommend Project Aura to a colleague?
                    </p>

                    {/* NPS Score Buttons */}
                    <div className="flex justify-center gap-1 mb-4">
                      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((score) => (
                        <button
                          key={score}
                          onClick={() => setNpsScore(score)}
                          className={`w-10 h-10 rounded-lg font-medium transition-all ${
                            npsScore === score
                              ? score <= 6
                                ? 'bg-critical-500 text-white'
                                : score <= 8
                                ? 'bg-warning-500 text-white'
                                : 'bg-olive-500 text-white'
                              : 'bg-surface-100 dark:bg-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-600'
                          }`}
                        >
                          {score}
                        </button>
                      ))}
                    </div>

                    {/* Score labels */}
                    <div className="flex justify-between text-xs text-surface-500 dark:text-surface-400 mb-6 px-1">
                      <span>{NPS_LABELS[0]}</span>
                      <span>{NPS_LABELS[5]}</span>
                      <span>{NPS_LABELS[10]}</span>
                    </div>

                    {/* Comment */}
                    <textarea
                      value={npsComment}
                      onChange={(e) => setNpsComment(e.target.value)}
                      placeholder="Tell us more about your rating (optional)"
                      rows={3}
                      className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
                    />

                    {error && (
                      <p className="mt-2 text-sm text-critical-600 dark:text-critical-400">{error}</p>
                    )}
                  </div>
                ) : feedbackType ? (
                  /* Feedback Form */
                  <div className="space-y-4">
                    <button
                      onClick={() => setFeedbackType(null)}
                      className="flex items-center text-sm text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-300"
                    >
                      <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                      Back
                    </button>

                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Title <span className="text-critical-500">*</span>
                      </label>
                      <input
                        type="text"
                        name="title"
                        value={formData.title}
                        onChange={handleInputChange}
                        placeholder="Brief summary of your feedback"
                        className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
                        maxLength={200}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                        Description <span className="text-critical-500">*</span>
                      </label>
                      <textarea
                        name="description"
                        value={formData.description}
                        onChange={handleInputChange}
                        placeholder="Please provide as much detail as possible..."
                        rows={4}
                        className="w-full px-3 py-2 border border-surface-300 dark:border-surface-600 rounded-lg bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 placeholder-surface-400 focus:ring-2 focus:ring-aura-500 focus:border-transparent"
                        maxLength={5000}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                        Related Areas
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {commonTags.map((tag) => (
                          <button
                            key={tag}
                            onClick={() => handleTagToggle(tag)}
                            className={`px-3 py-1 rounded-full text-sm transition-colors ${
                              formData.tags.includes(tag)
                                ? 'bg-aura-100 dark:bg-aura-900/30 text-aura-700 dark:text-aura-400 border border-aura-300 dark:border-aura-700'
                                : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-600'
                            }`}
                          >
                            {tag}
                          </button>
                        ))}
                      </div>
                    </div>

                    {error && (
                      <p className="text-sm text-critical-600 dark:text-critical-400">{error}</p>
                    )}
                  </div>
                ) : (
                  /* Type Selection */
                  <div className="space-y-3">
                    {FEEDBACK_TYPES.map((type) => (
                      <button
                        key={type.type}
                        onClick={() => handleSelectType(type.type)}
                        className="w-full flex items-center p-3 rounded-lg border border-surface-200 dark:border-surface-600 hover:border-aura-300 dark:hover:border-aura-700 hover:bg-aura-50 dark:hover:bg-aura-900/20 transition-colors text-left"
                      >
                        <span className="text-2xl mr-3">{type.icon}</span>
                        <div>
                          <div className="font-medium text-surface-900 dark:text-surface-100">{type.label}</div>
                          <div className="text-sm text-surface-500 dark:text-surface-400">{type.description}</div>
                        </div>
                      </button>
                    ))}

                    <div className="border-t border-surface-200 dark:border-surface-700 pt-3 mt-3">
                      <button
                        onClick={() => setShowNPS(true)}
                        className="w-full flex items-center p-3 rounded-lg border border-surface-200 dark:border-surface-600 hover:border-olive-300 dark:hover:border-olive-700 hover:bg-olive-50 dark:hover:bg-olive-900/20 transition-colors text-left"
                      >
                        <span className="text-2xl mr-3">📊</span>
                        <div>
                          <div className="font-medium text-surface-900 dark:text-surface-100">Take NPS Survey</div>
                          <div className="text-sm text-surface-500 dark:text-surface-400">Help us measure satisfaction</div>
                        </div>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Footer */}
              {!submitSuccess && (feedbackType || showNPS) && (
                <div className="bg-surface-50 dark:bg-surface-900 px-6 py-4 flex justify-end gap-3">
                  <button
                    onClick={handleClose}
                    className="px-4 py-2 text-surface-700 dark:text-surface-300 hover:text-surface-900 dark:hover:text-surface-100"
                    disabled={isSubmitting}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={showNPS ? handleSubmitNPS : handleSubmitFeedback}
                    disabled={isSubmitting}
                    className="px-4 py-2 bg-aura-600 text-white rounded-lg hover:bg-aura-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    {isSubmitting ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Submitting...
                      </>
                    ) : (
                      'Submit'
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default FeedbackWidget;
