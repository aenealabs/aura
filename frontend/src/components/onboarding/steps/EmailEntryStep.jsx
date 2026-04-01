/**
 * Project Aura - Email Entry Step
 *
 * Step 1 of the Team Invite Wizard.
 * Multi-input field for entering email addresses.
 */

import { useState, useCallback, useRef } from 'react';
import { XMarkIcon, PlusIcon, EnvelopeIcon } from '@heroicons/react/24/outline';

const EmailEntryStep = ({ emails, onEmailsChange, onNext }) => {
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  // Email validation regex
  const isValidEmail = (email) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const addEmail = useCallback(() => {
    const email = inputValue.trim().toLowerCase();

    if (!email) return;

    if (!isValidEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    if (emails.includes(email)) {
      setError('This email has already been added');
      return;
    }

    onEmailsChange([...emails, email]);
    setInputValue('');
    setError('');
    inputRef.current?.focus();
  }, [inputValue, emails, onEmailsChange]);

  const removeEmail = useCallback(
    (emailToRemove) => {
      onEmailsChange(emails.filter((e) => e !== emailToRemove));
    },
    [emails, onEmailsChange]
  );

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        addEmail();
      } else if (e.key === 'Backspace' && !inputValue && emails.length > 0) {
        // Remove last email on backspace when input is empty
        onEmailsChange(emails.slice(0, -1));
      }
    },
    [addEmail, inputValue, emails, onEmailsChange]
  );

  const handlePaste = useCallback(
    (e) => {
      e.preventDefault();
      const text = e.clipboardData.getData('text');

      // Split by common delimiters (comma, semicolon, newline, space)
      const pastedEmails = text
        .split(/[,;\n\s]+/)
        .map((email) => email.trim().toLowerCase())
        .filter((email) => email && isValidEmail(email))
        .filter((email) => !emails.includes(email));

      if (pastedEmails.length > 0) {
        onEmailsChange([...emails, ...pastedEmails]);
        setInputValue('');
        setError('');
      }
    },
    [emails, onEmailsChange]
  );

  const handleNext = useCallback(() => {
    if (emails.length === 0) {
      setError('Please add at least one email address');
      return;
    }
    onNext();
  }, [emails, onNext]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
          Invite team members
        </h2>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-400">
          Enter email addresses of people you want to invite to your organization.
        </p>
      </div>

      {/* Email input area */}
      <div className="space-y-2">
        <label
          htmlFor="email-input"
          className="block text-sm font-medium text-surface-700 dark:text-surface-300"
        >
          Email addresses
        </label>

        <div className="min-h-[120px] p-3 border border-surface-200 dark:border-surface-700 rounded-lg bg-white dark:bg-surface-800 focus-within:ring-2 focus-within:ring-aura-500 focus-within:border-aura-500 transition-all">
          {/* Email tags */}
          <div className="flex flex-wrap gap-2 mb-2">
            {emails.map((email) => (
              <span
                key={email}
                className="inline-flex items-center gap-1 px-2 py-1 text-sm bg-aura-50 dark:bg-aura-900/20 text-aura-700 dark:text-aura-300 rounded-md"
              >
                <EnvelopeIcon className="w-3.5 h-3.5" />
                {email}
                <button
                  onClick={() => removeEmail(email)}
                  className="p-0.5 rounded hover:bg-aura-100 dark:hover:bg-aura-900/40"
                  aria-label={`Remove ${email}`}
                >
                  <XMarkIcon className="w-3.5 h-3.5" />
                </button>
              </span>
            ))}
          </div>

          {/* Input field */}
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              id="email-input"
              type="email"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                setError('');
              }}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={
                emails.length === 0
                  ? 'Enter email addresses...'
                  : 'Add another email...'
              }
              className="flex-1 bg-transparent text-sm text-surface-900 dark:text-surface-100 placeholder-surface-400 dark:placeholder-surface-500 outline-none"
              autoComplete="off"
            />
            <button
              onClick={addEmail}
              className="p-1.5 text-surface-400 hover:text-aura-600 dark:hover:text-aura-400 rounded-md hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
              aria-label="Add email"
            >
              <PlusIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <p className="text-sm text-critical-600 dark:text-critical-400">{error}</p>
        )}

        {/* Help text */}
        <p className="text-xs text-surface-500 dark:text-surface-400">
          Press Enter or comma to add an email. You can also paste multiple emails at once.
        </p>
      </div>

      {/* Count */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-surface-600 dark:text-surface-400">
          {emails.length} {emails.length === 1 ? 'person' : 'people'} to invite
        </span>

        <button
          onClick={handleNext}
          disabled={emails.length === 0}
          className="px-4 py-2 bg-aura-600 hover:bg-aura-700 disabled:bg-surface-300 dark:disabled:bg-surface-700 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
        >
          Continue
        </button>
      </div>
    </div>
  );
};

export default EmailEntryStep;
