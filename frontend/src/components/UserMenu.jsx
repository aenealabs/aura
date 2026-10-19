import { useAuth } from '../context/AuthContext';
import Menu, { MenuItem, MenuLabel, MenuSeparator } from './shared/Menu';
import {
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  Cog6ToothIcon,
  ShieldCheckIcon,
  ChevronUpDownIcon,
} from '@heroicons/react/24/outline';

const UserMenu = ({ collapsed = false }) => {
  const { user, logout, isAuthenticated } = useAuth();
  if (!isAuthenticated || !user) {
    return null;
  }

  // Get role badge color
  const getRoleBadgeColor = (role) => {
    switch (role) {
      case 'admin':
        return 'bg-aura-100 text-aura-800 dark:bg-aura-900/40 dark:text-aura-300';
      case 'security-engineer':
        return 'bg-critical-100 text-critical-800 dark:bg-critical-900/40 dark:text-critical-300';
      case 'developer':
        return 'bg-olive-100 text-olive-800 dark:bg-olive-900/40 dark:text-olive-300';
      default:
        return 'bg-surface-100 text-surface-800 dark:bg-surface-700 dark:text-surface-300';
    }
  };

  // Get initials from name or email
  const getInitials = () => {
    if (user.name) {
      return user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    }
    return user.email?.[0]?.toUpperCase() || 'U';
  };

  const name = user.name || user.email?.split('@')[0];

  return (
    <Menu
      side="top"
      className={collapsed ? '' : 'w-[var(--radix-dropdown-menu-trigger-width)]'}
      trigger={
        <button
          type="button"
          aria-label={`Account menu for ${name}`}
          className={`flex items-center gap-3 w-full p-2 rounded-xl hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)] hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-aura-500 ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          {/* Avatar */}
          <div className="flex-shrink-0 w-9 h-9 bg-black rounded-full flex items-center justify-center text-white font-medium text-sm">
            {getInitials()}
          </div>

          {/* User info (hidden when collapsed) */}
          {!collapsed && (
            <>
              <div className="flex-1 text-left min-w-0">
                <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
                  {name}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400 truncate">{user.email}</p>
              </div>
              <ChevronUpDownIcon className="w-5 h-5 text-surface-400 dark:text-surface-500 flex-shrink-0" />
            </>
          )}
        </button>
      }
    >
      {/* User info header */}
      <MenuLabel className="px-4 py-3 border-b border-surface-100/50 dark:border-surface-700/30">
        <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">{name}</p>
        <p className="text-xs text-surface-500 dark:text-surface-400 truncate">{user.email}</p>
        {user.role && (
          <span
            className={`inline-flex items-center mt-2 px-2 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor(
              user.role
            )}`}
          >
            <ShieldCheckIcon className="w-3 h-3 mr-1" />
            {user.role}
          </span>
        )}
      </MenuLabel>

      {/* Menu items */}
      <div className="py-1 px-1">
        <MenuItem asChild>
          <a href="/settings">
            <Cog6ToothIcon className="w-5 h-5 text-surface-400 dark:text-surface-500" />
            Settings
          </a>
        </MenuItem>
        <MenuItem asChild>
          <a href="/profile">
            <UserCircleIcon className="w-5 h-5 text-surface-400 dark:text-surface-500" />
            Profile
          </a>
        </MenuItem>
      </div>

      {/* Logout */}
      <MenuSeparator className="!my-0" />
      <div className="py-1 px-1">
        <MenuItem tone="danger" onSelect={logout}>
          <ArrowRightOnRectangleIcon className="w-5 h-5" />
          Sign out
        </MenuItem>
      </div>
    </Menu>
  );
};

export default UserMenu;
