/**
 * Tests for EmailEntryStep component
 *
 * Tests step 1 of the Team Invite Wizard including:
 * - Header display (title, description)
 * - Email input field
 * - Adding emails (Enter, comma, plus button)
 * - Email validation
 * - Duplicate detection
 * - Email tag display and removal
 * - Backspace to remove last email
 * - Paste handling
 * - Error messages
 * - Count display
 * - Continue button state and navigation
 * - Placeholder text changes
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import EmailEntryStep from './EmailEntryStep';

describe('EmailEntryStep', () => {
  const defaultProps = {
    emails: [],
    onEmailsChange: vi.fn(),
    onNext: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Header Display', () => {
    test('displays title', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByText('Invite team members')).toBeInTheDocument();
    });

    test('displays description', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(
        screen.getByText('Enter email addresses of people you want to invite to your organization.')
      ).toBeInTheDocument();
    });

    test('displays label for email input', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByText('Email addresses')).toBeInTheDocument();
    });
  });

  describe('Email Input', () => {
    test('renders email input field', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    test('input has correct type', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByRole('textbox')).toHaveAttribute('type', 'email');
    });

    test('displays empty placeholder when no emails', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByPlaceholderText('Enter email addresses...')).toBeInTheDocument();
    });

    test('displays different placeholder when emails exist', () => {
      render(<EmailEntryStep {...defaultProps} emails={['test@example.com']} />);

      expect(screen.getByPlaceholderText('Add another email...')).toBeInTheDocument();
    });

    test('updates input value on change', () => {
      render(<EmailEntryStep {...defaultProps} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'user@test.com' } });

      expect(input).toHaveValue('user@test.com');
    });
  });

  describe('Adding Emails', () => {
    test('adds email on Enter key', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'test@example.com' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(onEmailsChange).toHaveBeenCalledWith(['test@example.com']);
    });

    test('adds email on comma key', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'test@example.com' } });
      fireEvent.keyDown(input, { key: ',' });

      expect(onEmailsChange).toHaveBeenCalledWith(['test@example.com']);
    });

    test('adds email on plus button click', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'test@example.com' } });
      fireEvent.click(screen.getByLabelText('Add email'));

      expect(onEmailsChange).toHaveBeenCalledWith(['test@example.com']);
    });

    test('converts email to lowercase', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'Test@EXAMPLE.com' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(onEmailsChange).toHaveBeenCalledWith(['test@example.com']);
    });

    test('trims whitespace from email', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '  test@example.com  ' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(onEmailsChange).toHaveBeenCalledWith(['test@example.com']);
    });

    test('does not add empty email', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(onEmailsChange).not.toHaveBeenCalled();
    });

    test('appends to existing emails', () => {
      const onEmailsChange = vi.fn();
      render(
        <EmailEntryStep
          {...defaultProps}
          emails={['first@example.com']}
          onEmailsChange={onEmailsChange}
        />
      );

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'second@example.com' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(onEmailsChange).toHaveBeenCalledWith(['first@example.com', 'second@example.com']);
    });
  });

  describe('Email Validation', () => {
    test('shows error for invalid email format', () => {
      render(<EmailEntryStep {...defaultProps} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'invalid-email' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(screen.getByText('Please enter a valid email address')).toBeInTheDocument();
    });

    test('shows error for email without @', () => {
      render(<EmailEntryStep {...defaultProps} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'nodomain.com' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(screen.getByText('Please enter a valid email address')).toBeInTheDocument();
    });

    test('shows error for email without domain', () => {
      render(<EmailEntryStep {...defaultProps} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'user@' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(screen.getByText('Please enter a valid email address')).toBeInTheDocument();
    });

    test('clears error when input changes', () => {
      render(<EmailEntryStep {...defaultProps} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'invalid' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(screen.getByText('Please enter a valid email address')).toBeInTheDocument();

      fireEvent.change(input, { target: { value: 'valid@example.com' } });

      expect(screen.queryByText('Please enter a valid email address')).not.toBeInTheDocument();
    });
  });

  describe('Duplicate Detection', () => {
    test('shows error for duplicate email', () => {
      render(<EmailEntryStep {...defaultProps} emails={['existing@example.com']} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'existing@example.com' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(screen.getByText('This email has already been added')).toBeInTheDocument();
    });

    test('detects duplicates case-insensitively', () => {
      render(<EmailEntryStep {...defaultProps} emails={['existing@example.com']} />);

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'EXISTING@EXAMPLE.COM' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(screen.getByText('This email has already been added')).toBeInTheDocument();
    });

    test('does not call onEmailsChange for duplicate', () => {
      const onEmailsChange = vi.fn();
      render(
        <EmailEntryStep
          {...defaultProps}
          emails={['existing@example.com']}
          onEmailsChange={onEmailsChange}
        />
      );

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'existing@example.com' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(onEmailsChange).not.toHaveBeenCalled();
    });
  });

  describe('Email Tags', () => {
    test('displays email tags for added emails', () => {
      render(
        <EmailEntryStep {...defaultProps} emails={['user1@example.com', 'user2@example.com']} />
      );

      expect(screen.getByText('user1@example.com')).toBeInTheDocument();
      expect(screen.getByText('user2@example.com')).toBeInTheDocument();
    });

    test('each tag has remove button', () => {
      render(<EmailEntryStep {...defaultProps} emails={['test@example.com']} />);

      expect(screen.getByLabelText('Remove test@example.com')).toBeInTheDocument();
    });

    test('removes email when X button is clicked', () => {
      const onEmailsChange = vi.fn();
      render(
        <EmailEntryStep
          {...defaultProps}
          emails={['first@example.com', 'second@example.com']}
          onEmailsChange={onEmailsChange}
        />
      );

      fireEvent.click(screen.getByLabelText('Remove first@example.com'));

      expect(onEmailsChange).toHaveBeenCalledWith(['second@example.com']);
    });

    test('each tag has envelope icon', () => {
      const { container } = render(
        <EmailEntryStep {...defaultProps} emails={['test@example.com']} />
      );

      // Each tag should have an envelope icon (w-3.5 h-3.5)
      const envelopeIcons = container.querySelectorAll('.w-3\\.5.h-3\\.5');
      expect(envelopeIcons.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Backspace Removal', () => {
    test('removes last email on backspace when input is empty', () => {
      const onEmailsChange = vi.fn();
      render(
        <EmailEntryStep
          {...defaultProps}
          emails={['first@example.com', 'last@example.com']}
          onEmailsChange={onEmailsChange}
        />
      );

      const input = screen.getByRole('textbox');
      fireEvent.keyDown(input, { key: 'Backspace' });

      expect(onEmailsChange).toHaveBeenCalledWith(['first@example.com']);
    });

    test('does not remove email on backspace when input has text', () => {
      const onEmailsChange = vi.fn();
      render(
        <EmailEntryStep
          {...defaultProps}
          emails={['test@example.com']}
          onEmailsChange={onEmailsChange}
        />
      );

      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'typing' } });
      fireEvent.keyDown(input, { key: 'Backspace' });

      expect(onEmailsChange).not.toHaveBeenCalled();
    });

    test('does nothing on backspace when no emails exist', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.keyDown(input, { key: 'Backspace' });

      expect(onEmailsChange).not.toHaveBeenCalled();
    });
  });

  describe('Paste Handling', () => {
    test('adds multiple emails from paste', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.paste(input, {
        clipboardData: {
          getData: () => 'first@example.com, second@example.com',
        },
      });

      expect(onEmailsChange).toHaveBeenCalledWith(['first@example.com', 'second@example.com']);
    });

    test('handles semicolon delimiter in paste', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.paste(input, {
        clipboardData: {
          getData: () => 'first@example.com; second@example.com',
        },
      });

      expect(onEmailsChange).toHaveBeenCalledWith(['first@example.com', 'second@example.com']);
    });

    test('handles newline delimiter in paste', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.paste(input, {
        clipboardData: {
          getData: () => 'first@example.com\nsecond@example.com',
        },
      });

      expect(onEmailsChange).toHaveBeenCalledWith(['first@example.com', 'second@example.com']);
    });

    test('filters out invalid emails from paste', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.paste(input, {
        clipboardData: {
          getData: () => 'valid@example.com, invalid-email, another@test.com',
        },
      });

      expect(onEmailsChange).toHaveBeenCalledWith(['valid@example.com', 'another@test.com']);
    });

    test('filters out duplicate emails from paste', () => {
      const onEmailsChange = vi.fn();
      render(
        <EmailEntryStep
          {...defaultProps}
          emails={['existing@example.com']}
          onEmailsChange={onEmailsChange}
        />
      );

      const input = screen.getByRole('textbox');
      fireEvent.paste(input, {
        clipboardData: {
          getData: () => 'existing@example.com, new@example.com',
        },
      });

      expect(onEmailsChange).toHaveBeenCalledWith(['existing@example.com', 'new@example.com']);
    });

    test('does not call onEmailsChange when all pasted emails are invalid', () => {
      const onEmailsChange = vi.fn();
      render(<EmailEntryStep {...defaultProps} onEmailsChange={onEmailsChange} />);

      const input = screen.getByRole('textbox');
      fireEvent.paste(input, {
        clipboardData: {
          getData: () => 'invalid, also-invalid, not-an-email',
        },
      });

      expect(onEmailsChange).not.toHaveBeenCalled();
    });

    test('does not call onEmailsChange when all pasted emails are duplicates', () => {
      const onEmailsChange = vi.fn();
      render(
        <EmailEntryStep
          {...defaultProps}
          emails={['existing@example.com']}
          onEmailsChange={onEmailsChange}
        />
      );

      const input = screen.getByRole('textbox');
      fireEvent.paste(input, {
        clipboardData: {
          getData: () => 'existing@example.com',
        },
      });

      expect(onEmailsChange).not.toHaveBeenCalled();
    });
  });

  describe('Count Display', () => {
    test('displays singular "person" for one email', () => {
      render(<EmailEntryStep {...defaultProps} emails={['test@example.com']} />);

      expect(screen.getByText('1 person to invite')).toBeInTheDocument();
    });

    test('displays plural "people" for multiple emails', () => {
      render(
        <EmailEntryStep {...defaultProps} emails={['first@example.com', 'second@example.com']} />
      );

      expect(screen.getByText('2 people to invite')).toBeInTheDocument();
    });

    test('displays "0 people" when no emails', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByText('0 people to invite')).toBeInTheDocument();
    });
  });

  describe('Continue Button', () => {
    test('displays Continue button', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
    });

    test('Continue button is disabled when no emails', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
    });

    test('Continue button is enabled when emails exist', () => {
      render(<EmailEntryStep {...defaultProps} emails={['test@example.com']} />);

      expect(screen.getByRole('button', { name: 'Continue' })).not.toBeDisabled();
    });

    test('calls onNext when Continue is clicked with emails', () => {
      const onNext = vi.fn();
      render(
        <EmailEntryStep {...defaultProps} emails={['test@example.com']} onNext={onNext} />
      );

      fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

      expect(onNext).toHaveBeenCalledTimes(1);
    });

    test('does not call onNext when Continue is clicked with no emails', () => {
      const onNext = vi.fn();
      render(<EmailEntryStep {...defaultProps} onNext={onNext} />);

      fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

      expect(onNext).not.toHaveBeenCalled();
    });

    // Note: Lines 85-86 (error message when handleNext called with no emails) are
    // defensive code that is unreachable because the Continue button is always
    // disabled when emails.length === 0. This is by design - the button state
    // prevents the invalid action, and the handler check is a safety fallback.
  });

  describe('Help Text', () => {
    test('displays help text about adding emails', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(
        screen.getByText('Press Enter or comma to add an email. You can also paste multiple emails at once.')
      ).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('input has associated label', () => {
      render(<EmailEntryStep {...defaultProps} />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('id', 'email-input');

      const label = screen.getByText('Email addresses');
      expect(label).toHaveAttribute('for', 'email-input');
    });

    test('add button has aria-label', () => {
      render(<EmailEntryStep {...defaultProps} />);

      expect(screen.getByLabelText('Add email')).toBeInTheDocument();
    });

    test('remove buttons have aria-labels with email', () => {
      render(
        <EmailEntryStep {...defaultProps} emails={['test@example.com', 'other@example.com']} />
      );

      expect(screen.getByLabelText('Remove test@example.com')).toBeInTheDocument();
      expect(screen.getByLabelText('Remove other@example.com')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    test('has focus ring on input container when focused', () => {
      const { container } = render(<EmailEntryStep {...defaultProps} />);

      const inputContainer = container.querySelector('.focus-within\\:ring-2');
      expect(inputContainer).toBeInTheDocument();
    });

    test('Continue button has correct disabled styling', () => {
      render(<EmailEntryStep {...defaultProps} />);

      const button = screen.getByRole('button', { name: 'Continue' });
      expect(button).toHaveClass('disabled:bg-surface-300');
      expect(button).toHaveClass('disabled:cursor-not-allowed');
    });
  });
});
