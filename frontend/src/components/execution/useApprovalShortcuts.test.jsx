/**
 * Tests for useApprovalShortcuts
 *
 * - A / D / M / T act on the current action, with the same calls as the approval card
 * - ? opens help; Esc asks to abort only while the execution can be aborted
 * - Ignored while typing, with modifier keys, while a dialog is open, with no current action,
 *   and while a request is in flight
 */

import { useState } from 'react';
import { render, renderHook, fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, afterEach } from 'vitest';
import useApprovalShortcuts from './useApprovalShortcuts';
import Modal, { ModalTitle } from '../shared/Modal';

const action = { action_id: 'act-1', type: 'file_write' };

function setup(overrides = {}) {
  const props = {
    currentAction: action,
    busy: false,
    canAbort: true,
    onApprove: vi.fn(),
    onDeny: vi.fn(),
    onModify: vi.fn(),
    onTrust: vi.fn(),
    onHelp: vi.fn(),
    onAbortRequest: vi.fn(),
    ...overrides,
  };
  renderHook(() => useApprovalShortcuts(props));
  return props;
}

const press = (key, init = {}, target = window) => fireEvent.keyDown(target, { key, ...init });

afterEach(() => {
  document.body.innerHTML = '';
});

describe('useApprovalShortcuts', () => {
  test.each([
    ['a', 'onApprove'], ['A', 'onApprove'], ['d', 'onDeny'], ['m', 'onModify'], ['t', 'onTrust'],
  ])('%s calls %s with the current action', (key, handler) => {
    const props = setup();
    press(key);
    expect(props[handler]).toHaveBeenCalledWith(action);
  });

  test('? opens the help', () => {
    const props = setup();
    press('?');
    expect(props.onHelp).toHaveBeenCalledTimes(1);
  });

  test('Esc asks to abort, and only while the execution can be aborted', () => {
    const props = setup();
    press('Escape');
    expect(props.onAbortRequest).toHaveBeenCalledTimes(1);
    const idle = setup({ canAbort: false });
    press('Escape');
    expect(idle.onAbortRequest).not.toHaveBeenCalled();
  });

  test('ignored while typing in a field', () => {
    const props = setup();
    const input = document.createElement('textarea');
    document.body.appendChild(input);
    press('a', {}, input);
    press('Escape', {}, input);
    expect(props.onApprove).not.toHaveBeenCalled();
    expect(props.onAbortRequest).not.toHaveBeenCalled();
  });

  test('ignored with Ctrl, Cmd, or Alt held', () => {
    const props = setup();
    press('a', { ctrlKey: true });
    press('d', { metaKey: true });
    press('m', { altKey: true });
    expect(props.onApprove).not.toHaveBeenCalled();
    expect(props.onDeny).not.toHaveBeenCalled();
    expect(props.onModify).not.toHaveBeenCalled();
  });

  test('ignored while a dialog is open, so Esc only closes the dialog', () => {
    const props = setup();
    const dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    document.body.appendChild(dialog);
    press('a');
    press('Escape');
    expect(props.onApprove).not.toHaveBeenCalled();
    expect(props.onAbortRequest).not.toHaveBeenCalled();
  });

  test('A/D/M/T do nothing with no action awaiting approval or a request in flight', () => {
    const none = setup({ currentAction: null });
    press('a');
    expect(none.onApprove).not.toHaveBeenCalled();
    const busy = setup({ busy: true });
    press('d');
    expect(busy.onDeny).not.toHaveBeenCalled();
  });

  test('with a real dialog open, Esc closes the dialog and does not ask to abort', async () => {
    const user = userEvent.setup();
    const onAbortRequest = vi.fn();
    function Panel() {
      const [help, setHelp] = useState(false);
      useApprovalShortcuts({
        currentAction: action, canAbort: true, onApprove() {}, onDeny() {}, onModify() {},
        onTrust() {}, onHelp: () => setHelp(true), onAbortRequest,
      });
      return (
        <Modal open={help} onClose={() => setHelp(false)}>
          <ModalTitle>Keyboard Shortcuts</ModalTitle>
        </Modal>
      );
    }
    render(<Panel />);
    await user.keyboard('?');
    expect(screen.getByRole('dialog', { name: 'Keyboard Shortcuts' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(onAbortRequest).not.toHaveBeenCalled();
    await user.keyboard('{Escape}'); // no dialog now: Esc asks to abort
    expect(onAbortRequest).toHaveBeenCalledTimes(1);
  });
});
