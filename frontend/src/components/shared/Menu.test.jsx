/**
 * Tests for the shared Menu (Radix Dropdown Menu)
 *
 * - Opens from the keyboard and exposes menu / menuitem roles
 * - Arrow keys move between items; Enter selects
 * - Escape closes and returns focus to the trigger
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import Menu, { MenuItem, MenuLabel, MenuSeparator } from './Menu';

function renderMenu(onSignOut = vi.fn()) {
  render(
    <Menu trigger={<button>Account</button>}>
      <MenuLabel>Jordan Lee</MenuLabel>
      <MenuItem onSelect={() => {}}>Settings</MenuItem>
      <MenuSeparator />
      <MenuItem tone="danger" onSelect={onSignOut}>Sign out</MenuItem>
    </Menu>
  );
  return onSignOut;
}

describe('Menu', () => {
  test('opens from the keyboard as a menu with menu items', async () => {
    const user = userEvent.setup();
    renderMenu();
    screen.getByRole('button', { name: 'Account' }).focus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.getAllByRole('menuitem').map((i) => i.textContent)).toEqual(['Settings', 'Sign out']);
  });

  test('arrow keys move between items and Enter selects', async () => {
    const user = userEvent.setup();
    const onSignOut = renderMenu();
    screen.getByRole('button', { name: 'Account' }).focus();
    await user.keyboard('{ArrowDown}');
    await user.keyboard('{ArrowDown}');
    expect(document.activeElement).toHaveTextContent('Sign out');
    await user.keyboard('{Enter}');
    expect(onSignOut).toHaveBeenCalledTimes(1);
  });

  test('Escape closes it and returns focus to the trigger', async () => {
    const user = userEvent.setup();
    renderMenu();
    const trigger = screen.getByRole('button', { name: 'Account' });
    trigger.focus();
    await user.keyboard('{Enter}');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);
  });
});
