/**
 * Project Aura - Team Invite Wizard
 *
 * P5: Multi-step wizard for inviting team members.
 *
 * Steps:
 * 1. Enter email addresses
 * 2. Assign roles
 * 3. Review & personalize message
 * 4. Completion
 *
 * Features:
 * - Multi-email input with validation
 * - Role assignment per invitee
 * - Custom message support
 * - Shareable invite link
 */

import { useState, useCallback, useEffect, Fragment } from 'react';
import { createPortal } from 'react-dom';
import { XMarkIcon } from '@heroicons/react/24/outline';

import EmailEntryStep from './steps/EmailEntryStep';
import RoleAssignmentStep from './steps/RoleAssignmentStep';
import InviteReviewStep from './steps/InviteReviewStep';
import InviteCompletionStep from './steps/InviteCompletionStep';
import { useOnboarding } from '../../context/OnboardingContext';

const STEPS = [
  { id: 'emails', title: 'Add Emails' },
  { id: 'roles', title: 'Assign Roles' },
  { id: 'review', title: 'Review' },
  { id: 'complete', title: 'Done' },
];

const TeamInviteWizard = ({ isOpen, onClose }) => {
  const { completeChecklistItem } = useOnboarding();

  // Wizard state
  const [currentStep, setCurrentStep] = useState(0);
  const [emails, setEmails] = useState([]);
  const [invitees, setInvitees] = useState([]);
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [inviteLink, setInviteLink] = useState('');

  // Reset state when opened
  useEffect(() => {
    if (isOpen) {
      setCurrentStep(0);
      setEmails([]);
      setInvitees([]);
      setMessage('');
      setIsSending(false);
      setInviteLink('');
    }
  }, [isOpen]);

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && currentStep !== 3) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentStep, onClose]);

  // Navigate to roles step
  const handleEmailsComplete = useCallback(() => {
    // Convert emails to invitees with default role
    setInvitees(emails.map((email) => ({ email, role: 'developer' })));
    setCurrentStep(1);
  }, [emails]);

  // Navigate to review step
  const handleRolesComplete = useCallback(() => {
    setCurrentStep(2);
  }, []);

  // Send invitations
  const handleSend = useCallback(async (customMessage) => {
    setIsSending(true);

    try {
      // TODO: Replace with actual API call
      // const response = await sendInvitations(invitees, customMessage);

      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1500));

      // Generate mock invite link
      const mockLink = `https://app.aenealabs.com/invite/${Math.random().toString(36).substring(2, 10)}`;
      setInviteLink(mockLink);

      // Mark checklist item complete
      completeChecklistItem('invite_team_member');

      setCurrentStep(3);
    } catch (error) {
      console.error('Failed to send invitations:', error);
      // Handle error (show toast, etc.)
    } finally {
      setIsSending(false);
    }
  }, [invitees, completeChecklistItem]);

  // Reset and start over
  const handleAddMore = useCallback(() => {
    setCurrentStep(0);
    setEmails([]);
    setInvitees([]);
    setMessage('');
    setInviteLink('');
  }, []);

  // Navigate back
  const goBack = useCallback(() => {
    setCurrentStep((prev) => Math.max(0, prev - 1));
  }, []);

  // Handle backdrop click
  const handleBackdropClick = useCallback(
    (e) => {
      if (e.target === e.currentTarget && currentStep !== 3) {
        onClose();
      }
    },
    [currentStep, onClose]
  );

  if (!isOpen) {
    return null;
  }

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return (
          <EmailEntryStep
            emails={emails}
            onEmailsChange={setEmails}
            onNext={handleEmailsComplete}
          />
        );
      case 1:
        return (
          <RoleAssignmentStep
            invitees={invitees}
            onInviteesChange={setInvitees}
            onNext={handleRolesComplete}
            onBack={goBack}
          />
        );
      case 2:
        return (
          <InviteReviewStep
            invitees={invitees}
            message={message}
            onMessageChange={setMessage}
            onSend={handleSend}
            onBack={goBack}
            isSending={isSending}
          />
        );
      case 3:
        return (
          <InviteCompletionStep
            invitees={invitees}
            inviteLink={inviteLink}
            onClose={onClose}
            onAddMore={handleAddMore}
          />
        );
      default:
        return null;
    }
  };

  const modal = (
    <div
      className="fixed inset-0 z-50 overflow-y-auto"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="team-invite-title"
    >
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 transition-opacity" />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-lg bg-white dark:bg-surface-900 rounded-xl shadow-xl transform transition-all">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-surface-700">
            <h1
              id="team-invite-title"
              className="text-lg font-semibold text-surface-900 dark:text-surface-100"
            >
              Invite Team Members
            </h1>
            {currentStep !== 3 && (
              <button
                onClick={onClose}
                className="p-1 rounded-lg text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800"
                aria-label="Close"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Progress indicator */}
          {currentStep < 3 && (
            <div className="px-6 py-3 border-b border-surface-200 dark:border-surface-700">
              <nav className="flex items-center justify-center">
                {STEPS.slice(0, 3).map((step, index) => {
                  const isActive = currentStep === index;
                  const isCompleted = currentStep > index;
                  const isLast = index === 2;

                  return (
                    <Fragment key={step.id}>
                      <div className="flex items-center">
                        <div
                          className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium transition-colors ${
                            isActive
                              ? 'bg-aura-600 text-white'
                              : isCompleted
                              ? 'bg-olive-500 text-white'
                              : 'bg-surface-200 dark:bg-surface-700 text-surface-500 dark:text-surface-400'
                          }`}
                        >
                          {isCompleted ? (
                            <svg
                              className="w-3.5 h-3.5"
                              fill="currentColor"
                              viewBox="0 0 20 20"
                            >
                              <path
                                fillRule="evenodd"
                                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                clipRule="evenodd"
                              />
                            </svg>
                          ) : (
                            index + 1
                          )}
                        </div>
                        <span
                          className={`ml-2 text-xs hidden sm:inline ${
                            isActive
                              ? 'text-surface-900 dark:text-surface-100 font-medium'
                              : 'text-surface-500 dark:text-surface-400'
                          }`}
                        >
                          {step.title}
                        </span>
                      </div>
                      {!isLast && (
                        <div
                          className={`w-8 sm:w-12 h-0.5 mx-2 ${
                            isCompleted
                              ? 'bg-olive-500'
                              : 'bg-surface-200 dark:bg-surface-700'
                          }`}
                        />
                      )}
                    </Fragment>
                  );
                })}
              </nav>
            </div>
          )}

          {/* Content */}
          <div className="px-6 py-6">{renderStep()}</div>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
};

export default TeamInviteWizard;
