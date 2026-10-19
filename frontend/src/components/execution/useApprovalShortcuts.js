/**
 * useApprovalShortcuts
 *
 * Keyboard shortcuts for the real-time execution panel, matching the buttons on the current
 * action's approval card:
 *
 *   A    approve the current action
 *   D    deny the current action
 *   M    modify the current action (opens the modify dialog)
 *   T    approve and trust this action type for the session
 *   ?    show the shortcuts help
 *   Esc  ask to abort the execution (the caller shows a confirmation)
 *
 * Shortcuts are ignored while typing in a field, with Ctrl, Cmd, or Alt held, while any dialog
 * is open (the dialog handles its own keys, including Escape), and, for A/D/M/T, when there is
 * no action awaiting approval or a request is already in flight.
 *
 * @module components/execution/useApprovalShortcuts
 */

import { useEffect } from 'react';

const ACTION_KEYS = { a: 'onApprove', d: 'onDeny', m: 'onModify', t: 'onTrust' };

function isTyping(target) {
  if (!target || !(target instanceof Element)) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

function dialogOpen() {
  return document.querySelector('[role="dialog"], [role="alertdialog"]') !== null;
}

/**
 * @param {Object} options
 * @param {Object|null} options.currentAction - The action awaiting approval, if any
 * @param {boolean} [options.busy] - A request is in flight; ignore A/D/M/T
 * @param {boolean} [options.canAbort] - The execution can be aborted; enables Esc
 * @param {function} options.onApprove - (action) => void
 * @param {function} options.onDeny - (action) => void
 * @param {function} options.onModify - (action) => void
 * @param {function} options.onTrust - (action) => void
 * @param {function} options.onHelp - () => void
 * @param {function} options.onAbortRequest - () => void; show a confirmation, do not abort here
 */
export default function useApprovalShortcuts({
  currentAction,
  busy = false,
  canAbort = false,
  onApprove,
  onDeny,
  onModify,
  onTrust,
  onHelp,
  onAbortRequest,
}) {
  useEffect(() => {
    const handlers = { onApprove, onDeny, onModify, onTrust };

    const handleKeyDown = (e) => {
      // A dialog that handled the key (Radix prevents default on its Escape) or a modifier
      // combination is not a shortcut.
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      if (isTyping(e.target) || dialogOpen()) return;

      if (e.key === '?') {
        e.preventDefault();
        onHelp?.();
        return;
      }
      if (e.key === 'Escape') {
        if (canAbort) {
          e.preventDefault();
          onAbortRequest?.();
        }
        return;
      }

      const handler = handlers[ACTION_KEYS[e.key.toLowerCase()]];
      if (!handler || !currentAction || busy) return;
      e.preventDefault();
      handler(currentAction);
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentAction, busy, canAbort, onApprove, onDeny, onModify, onTrust, onHelp, onAbortRequest]);
}
