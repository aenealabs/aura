/**
 * Tests for UserMenu, built on the shared Menu
 *
 * - Hidden when signed out
 * - The account button opens a menu with Settings, Profile, and Sign out
 * - Sign out calls logout
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import UserMenu from './UserMenu';

const auth = { user: null, logout: vi.fn(), isAuthenticated: false };
vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }));

describe('UserMenu', () => {
  beforeEach(() => {
    auth.user = { name: 'Jordan Lee', email: 'jordan@example.com', role: 'admin' };
    auth.isAuthenticated = true;
    auth.logout = vi.fn();
  });

  test('renders nothing when signed out', () => {
    auth.isAuthenticated = false;
    const { container } = render(<UserMenu />);
    expect(container).toBeEmptyDOMElement();
  });

  test('opens an accessible account menu and signs out', async () => {
    const user = userEvent.setup();
    render(<UserMenu />);
    const trigger = screen.getByRole('button', { name: 'Account menu for Jordan Lee' });
    trigger.focus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Settings' })).toHaveAttribute('href', '/settings');
    expect(screen.getByRole('menuitem', { name: 'Profile' })).toHaveAttribute('href', '/profile');
    await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    expect(auth.logout).toHaveBeenCalledTimes(1);
  });
});
