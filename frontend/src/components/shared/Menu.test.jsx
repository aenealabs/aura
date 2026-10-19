/**
 * Tests for the shared Menu (Radix Dropdown Menu)
 *
 * - Opens from the keyboard and exposes menu / menuitem roles
 * - Arrow keys move between items; Enter selects
 * - Escape closes and returns focus to the trigger
 * - Radio items pick one value and report which is checked
 * - An item can open a Modal; closing it returns focus to the trigger and leaves the page usable
 */

import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi } from 'vitest';
import Menu, {
  MenuItem, MenuLabel, MenuSeparator, MenuRadioGroup, MenuRadioItem,
} from './Menu';
import Modal, { ModalTitle } from './Modal';

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

  test('an item that opens a Modal returns focus to the trigger when the Modal closes', async () => {
    function Card() {
      const [editing, setEditing] = useState(false);
      return (
        <>
          <Menu trigger={<button>More actions</button>}>
            <MenuItem onSelect={() => setEditing(true)}>Edit</MenuItem>
          </Menu>
          <Modal open={editing} onClose={() => setEditing(false)}>
            <ModalTitle>Edit provider</ModalTitle>
            <button>Save</button>
          </Modal>
        </>
      );
    }
    const user = userEvent.setup();
    render(<Card />);
    const trigger = screen.getByRole('button', { name: 'More actions' });
    trigger.focus();
    await user.keyboard('{Enter}');
    await user.keyboard('{Enter}');
    expect(screen.getByRole('dialog', { name: 'Edit provider' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);
    expect(document.body.style.pointerEvents).not.toBe('none');
  });

  test('radio items pick one value and expose which is checked', async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <Menu trigger={<button>Repository</button>}>
        <MenuRadioGroup value="core" onValueChange={onValueChange}>
          <MenuRadioItem value="core">aura-core</MenuRadioItem>
          <MenuRadioItem value="web">aura-web</MenuRadioItem>
        </MenuRadioGroup>
      </Menu>
    );
    await user.click(screen.getByRole('button', { name: 'Repository' }));
    expect(screen.getByRole('menuitemradio', { name: 'aura-core' })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('menuitemradio', { name: 'aura-web' })).toHaveAttribute('aria-checked', 'false');
    await user.click(screen.getByRole('menuitemradio', { name: 'aura-web' }));
    expect(onValueChange).toHaveBeenCalledWith('web');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
