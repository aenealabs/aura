import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  Cog6ToothIcon,
  ShieldCheckIcon,
  ChevronUpDownIcon,
} from '@heroicons/react/24/outline';

const UserMenu = ({ collapsed = false }) => {
  const { user, logout, isAuthenticated } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

  return (
    <div ref={menuRef} className="relative">
      {/* User Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-3 w-full p-2 rounded-xl hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-200 ease-[var(--ease-tahoe)] hover:shadow-sm ${
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
                {user.name || user.email?.split('@')[0]}
              </p>
              <p className="text-xs text-surface-500 dark:text-surface-400 truncate">{user.email}</p>
            </div>
            <ChevronUpDownIcon className="w-5 h-5 text-surface-400 dark:text-surface-500 flex-shrink-0" />
          </>
        )}
      </button>

      {/* Dropdown Menu - Glass Style */}
      {isOpen && (
        <div
          className={`absolute bottom-full mb-2 ${
            collapsed ? 'left-0' : 'left-0 right-0'
          } min-w-[200px] rounded-xl py-1 z-50
            bg-white dark:bg-surface-800
            backdrop-blur-xl
            border border-white/50 dark:border-surface-700/50
            shadow-[var(--shadow-glass)]
          `}
        >
          {/* User info header */}
          <div className="px-4 py-3 border-b border-surface-100/50 dark:border-surface-700/30">
            <p className="text-sm font-medium text-surface-900 dark:text-surface-100 truncate">
              {user.name || user.email?.split('@')[0]}
            </p>
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
          </div>

          {/* Menu items */}
          <div className="py-1 px-1">
            <a
              href="/settings"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-150"
            >
              <Cog6ToothIcon className="w-5 h-5 text-surface-400 dark:text-surface-500" />
              Settings
            </a>
            <a
              href="/profile"
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-700 transition-all duration-150"
            >
              <UserCircleIcon className="w-5 h-5 text-surface-400 dark:text-surface-500" />
              Profile
            </a>
          </div>

          {/* Logout */}
          <div className="border-t border-surface-100/50 dark:border-surface-700/30 py-1 px-1">
            <button
              onClick={logout}
              className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-critical-600 dark:text-critical-400 hover:bg-critical-50/80 dark:hover:bg-critical-900/20 transition-all duration-150"
            >
              <ArrowRightOnRectangleIcon className="w-5 h-5" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserMenu;
