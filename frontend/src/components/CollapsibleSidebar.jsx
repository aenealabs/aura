import { useState, useEffect, createContext, useContext } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeIcon,
  PlusIcon,
  Cog6ToothIcon,
  ChevronLeftIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  BugAntIcon,
  PuzzlePieceIcon,
  CpuChipIcon,
  BellIcon,
  EyeIcon,
  BeakerIcon,
  CodeBracketIcon,
  ShareIcon,
  ChartBarIcon,
  CalendarDaysIcon,
  DocumentTextIcon,
  ScaleIcon,
  AdjustmentsHorizontalIcon,
  LightBulbIcon,
  CircleStackIcon,
  MagnifyingGlassCircleIcon,
} from '@heroicons/react/24/outline';
import UserMenu from './UserMenu';
import DarkModeToggle from './ui/DarkModeToggle';
import { useSecurityAlerts } from '../context/SecurityAlertsContext';
import { CommandPaletteTrigger } from './CommandPalette';
import { useDeveloperMode } from '../context/DeveloperModeContext';

// Create a context to pass down the expanded state, avoiding prop drilling
const SidebarContext = createContext();

// Logo component with animation
function AuraLogo({ expanded }) {
  return (
    <div className="flex items-center gap-2">
      {/* Logo mark - spiral logo */}
      <div className="relative flex-shrink-0">
        <img
          src="/assets/aura-spiral.png"
          alt="Aura Logo"
          className="w-10 h-10 object-contain"
        />
      </div>

      {/* Text - only visible when expanded */}
      <div
        className={`
          overflow-hidden transition-all duration-300 ease-smooth
          ${expanded ? 'w-auto opacity-100' : 'w-0 opacity-0'}
        `}
      >
        <span className="font-bold text-lg whitespace-nowrap">
          <span className="text-surface-900 dark:text-white">AURA</span>
        </span>
      </div>
    </div>
  );
}

// Section header for grouping nav items
function SectionHeader({ title, expanded }) {
  if (!expanded) return null;

  return (
    <div className="px-3 pt-4 pb-2">
      <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">
        {title}
      </span>
    </div>
  );
}

export default function CollapsibleSidebar() {
  // Read from localStorage or default to true (expanded)
  const [isExpanded, setIsExpanded] = useState(() => {
    const savedState = localStorage.getItem('sidebarExpanded');
    return savedState ? JSON.parse(savedState) : true;
  });

  // Get unacknowledged security alerts count
  const { unacknowledgedCount } = useSecurityAlerts();

  // Get developer mode state
  const { enabled: devModeEnabled } = useDeveloperMode();

  // Persist state to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('sidebarExpanded', JSON.stringify(isExpanded));
  }, [isExpanded]);

  return (
    <aside className="h-screen flex-shrink-0">
      <nav
        id="navigation"
        aria-label="Main navigation"
        className={`
          h-full flex flex-col
          glass-panel
          border-r border-surface-200/50 dark:border-surface-700/50
          transition-all duration-300 ease-smooth
          ${isExpanded ? 'w-64' : 'w-[72px]'}
        `}
      >
        {/* Header with logo and collapse button */}
        <div
          className={`
            p-4 border-b border-surface-100 dark:border-surface-700/50
            ${isExpanded ? 'flex items-center justify-between' : 'flex flex-col items-center gap-3'}
          `}
        >
          <AuraLogo expanded={isExpanded} />

          <button
            onClick={() => setIsExpanded((curr) => !curr)}
            className={`
              p-1.5 rounded-lg
              bg-surface-100 dark:bg-surface-700
              hover:bg-surface-200 dark:hover:bg-surface-600
              text-surface-500 dark:text-surface-400
              transition-all duration-200
            `}
            aria-label={isExpanded ? "Collapse sidebar" : "Expand sidebar"}
          >
            <ChevronLeftIcon
              className={`
                w-5 h-5 transition-transform duration-300
                ${!isExpanded && 'rotate-180'}
              `}
            />
          </button>
        </div>

        {/* Search - visible when expanded */}
        {isExpanded && (
          <div data-tour="sidebar-search" className="p-3 border-b border-surface-100 dark:border-surface-700/50">
            <CommandPaletteTrigger />
          </div>
        )}

        {/* New Project button - top position for maximum discoverability */}
        <div className="px-3 pt-3 pb-2">
          <Link
            to="/repositories?action=new"
            className={`
              group relative w-full flex items-center justify-center gap-2 h-10 px-4
              font-medium rounded-full
              transition-all duration-200 ease-[var(--ease-tahoe)]
              bg-gradient-to-r from-aura-500 to-aura-600
              hover:from-aura-600 hover:to-aura-700
              text-white shadow-sm hover:shadow-md hover:-translate-y-px
              active:scale-[0.98]
              focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
              dark:focus:ring-offset-surface-900
              ${!isExpanded ? 'px-2' : ''}
            `}
            aria-label="Create new project"
          >
            <PlusIcon className="w-5 h-5 flex-shrink-0" />
            <span
              className={`
                overflow-hidden whitespace-nowrap transition-all duration-300
                ${isExpanded ? 'w-auto opacity-100' : 'w-0 opacity-0'}
              `}
            >
              New Project
            </span>

            {/* Tooltip for collapsed state - glass style matching nav items */}
            {!isExpanded && (
              <div
                className={`
                  absolute left-full top-1/2 -translate-y-1/2 ml-3 z-50
                  rounded-xl px-3 py-2
                  bg-white dark:bg-surface-800
                  backdrop-blur-lg
                  border border-white/50 dark:border-surface-700/50
                  shadow-[var(--shadow-glass)]
                  text-surface-900 dark:text-surface-100
                  text-sm font-medium whitespace-nowrap
                  invisible opacity-0 -translate-x-2
                  transition-all duration-200 ease-[var(--ease-tahoe)]
                  group-hover:visible group-hover:opacity-100 group-hover:translate-x-0
                `}
              >
                New Project
                {/* Tooltip arrow */}
                <div
                  className="
                    absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1
                    w-2 h-2 rotate-45
                    bg-white dark:bg-surface-800
                    border-l border-b border-white/50 dark:border-surface-700/50
                  "
                />
              </div>
            )}
          </Link>
        </div>

        <SidebarContext.Provider value={{ isExpanded }}>
          {/* Main navigation */}
          <div data-tour="sidebar-nav" className="flex-1 overflow-y-auto overflow-x-hidden py-2">
            <SectionHeader title="Overview" expanded={isExpanded} />
            <ul className="px-3 space-y-1">
              <SidebarItem icon={<HomeIcon className="w-5 h-5" />} text="Dashboard" to="/" />
              <SidebarItem icon={<CodeBracketIcon className="w-5 h-5" />} text="Repositories" to="/repositories" />
              <SidebarItem icon={<BeakerIcon className="w-5 h-5" />} text="Sandboxes" to="/sandboxes" />
              <SidebarItem icon={<PuzzlePieceIcon className="w-5 h-5" />} text="Integrations" to="/integrations" />
            </ul>

            <SectionHeader title="Security" expanded={isExpanded} />
            <ul className="px-3 space-y-1">
              <SidebarItem
                icon={<ShieldCheckIcon className="w-5 h-5" />}
                text="Approvals"
                to="/approvals"
                badge={7}
                badgeColor="warning"
              />
              <SidebarItem
                icon={<ExclamationTriangleIcon className="w-5 h-5" />}
                text="Incidents"
                to="/incidents"
                badge={2}
                badgeColor="critical"
              />
              <SidebarItem icon={<BugAntIcon className="w-5 h-5" />} text="Red Team" to="/security/red-team" />
              <SidebarItem icon={<MagnifyingGlassCircleIcon className="w-5 h-5" />} text="Vuln Scanner" to="/security/scanner" />
              <SidebarItem
                icon={<BellIcon className="w-5 h-5" />}
                text="Alerts"
                to="/security/alerts"
                badge={unacknowledgedCount > 0 ? unacknowledgedCount : null}
                badgeColor="critical"
              />
              <SidebarItem
                icon={<ShieldExclamationIcon className="w-5 h-5" />}
                text="Validator"
                to="/validator"
              />
              <SidebarItem
                icon={<ScaleIcon className="w-5 h-5" />}
                text="AI Trust Center"
                to="/trust-center"
              />
              <SidebarItem
                icon={<AdjustmentsHorizontalIcon className="w-5 h-5" />}
                text="Guardrails"
                to="/guardrails"
              />
              <SidebarItem
                icon={<LightBulbIcon className="w-5 h-5" />}
                text="Explainability"
                to="/explainability"
              />
              <SidebarItem
                icon={<CircleStackIcon className="w-5 h-5" />}
                text="Capability Graph"
                to="/capability-graph"
              />
            </ul>

            <SectionHeader title="Intelligence" expanded={isExpanded} />
            <ul className="px-3 space-y-1">
              <SidebarItem icon={<ShareIcon className="w-5 h-5" />} text="Knowledge Graph" to="/graph" />
              <SidebarItem icon={<DocumentTextIcon className="w-5 h-5" />} text="Documentation" to="/documentation" />
              <SidebarItem icon={<CpuChipIcon className="w-5 h-5" />} text="Agents" to="/agents/registry" />
              <SidebarItem
                icon={<EyeIcon className="w-5 h-5" />}
                text="Mission Control"
                to="/agents/mission-control"
                badge={2}
                badgeColor="aura"
              />
              <SidebarItem icon={<CalendarDaysIcon className="w-5 h-5" />} text="Scheduling" to="/agents/scheduling" />
            </ul>

            <SectionHeader title="Observability" expanded={isExpanded} />
            <ul className="px-3 space-y-1">
              <SidebarItem icon={<ChartBarIcon className="w-5 h-5" />} text="Traces" to="/observability/traces" />
            </ul>
          </div>

          {/* User section */}
          <div className="border-t border-surface-100/50 dark:border-surface-700/30 p-3">
            <UserMenu collapsed={!isExpanded} />
          </div>

          {/* Bottom navigation */}
          <div className="border-t border-surface-100/50 dark:border-surface-700/30">
            <ul className="px-3 py-2 space-y-1">
              <SidebarItem icon={<Cog6ToothIcon className="w-5 h-5" />} text="Settings" to="/settings" dataTour="settings-link" />
            </ul>

            {/* Dark mode toggle */}
            <div className="px-3 pb-3">
              {isExpanded ? (
                <div className="flex items-center justify-between py-2 px-3 rounded-xl glass-card-subtle">
                  <span className="text-sm text-surface-600 dark:text-surface-400">Theme</span>
                  <DarkModeToggle />
                </div>
              ) : (
                <div className="flex justify-center">
                  <DarkModeToggle />
                </div>
              )}
            </div>

            {/* Developer Mode Indicator */}
            {devModeEnabled && (
              <div className="px-3 pb-3">
                {isExpanded ? (
                  <div className="flex items-center gap-2 py-2 px-3 rounded-xl bg-warning-50 dark:bg-warning-900/20 border border-warning-200 dark:border-warning-800">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-warning-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-warning-500"></span>
                    </span>
                    <span className="text-xs font-medium text-warning-700 dark:text-warning-300">Dev Mode</span>
                  </div>
                ) : (
                  <div className="flex justify-center">
                    <span className="relative flex h-3 w-3" title="Developer Mode Active">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-warning-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-warning-500"></span>
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </SidebarContext.Provider>
      </nav>
    </aside>
  );
}

export function SidebarItem({ icon, text, to, badge, badgeColor = 'aura', dataTour }) {
  const { isExpanded } = useContext(SidebarContext);
  const location = useLocation();

  // Determine if this item is active based on current path
  const isActive = to === '/'
    ? location.pathname === '/'
    : location.pathname.startsWith(to);

  const badgeColors = {
    aura: 'bg-aura-500 text-white',
    olive: 'bg-olive-500 text-white',
    warning: 'bg-warning-500 text-white',
    critical: 'bg-critical-500 text-white',
  };

  return (
    <li data-tour={dataTour}>
      <Link
        to={to}
        className={`
          relative flex items-center h-11 px-3
          font-medium rounded-xl cursor-pointer
          transition-all duration-200 ease-[var(--ease-tahoe)]
          group
          ${isActive
            ? 'glass-card-subtle text-aura-700 dark:text-aura-400 shadow-sm'
            : 'text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-700 hover:text-surface-900 dark:hover:text-surface-100 hover:shadow-sm hover:-translate-y-px'
          }
        `}
      >
        {/* Active indicator bar */}
        {isActive && (
          <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-aura-500 rounded-r-full" />
        )}

        {/* Icon */}
        <span className={`flex-shrink-0 ${isActive ? 'text-aura-600 dark:text-aura-400' : ''}`}>
          {icon}
        </span>

        {/* Text */}
        <span
          className={`
            overflow-hidden whitespace-nowrap transition-all duration-300
            ${isExpanded ? 'w-auto ml-3 opacity-100' : 'w-0 opacity-0'}
          `}
        >
          {text}
        </span>

        {/* Badge */}
        {badge !== undefined && badge !== null && (
          <span
            className={`
              ${isExpanded ? 'ml-auto' : 'absolute top-1 right-1'}
              min-w-[20px] h-5 px-1.5 rounded-full
              text-xs font-semibold flex items-center justify-center
              ${badgeColors[badgeColor]}
              transition-all duration-200
            `}
          >
            {badge}
          </span>
        )}

        {/* Tooltip for collapsed state - glass style */}
        {!isExpanded && (
          <div
            className={`
              absolute left-full top-1/2 -translate-y-1/2 ml-3 z-50
              rounded-xl px-3 py-2
              bg-white dark:bg-surface-800
              backdrop-blur-lg
              border border-white/50 dark:border-surface-700/50
              shadow-[var(--shadow-glass)]
              text-surface-900 dark:text-surface-100
              text-sm font-medium whitespace-nowrap
              invisible opacity-0 -translate-x-2
              transition-all duration-200 ease-[var(--ease-tahoe)]
              group-hover:visible group-hover:opacity-100 group-hover:translate-x-0
            `}
          >
            <div className="flex items-center gap-2">
              {text}
              {badge !== undefined && badge !== null && (
                <span className={`px-1.5 py-0.5 rounded text-xs ${badgeColors[badgeColor]}`}>
                  {badge}
                </span>
              )}
            </div>
            {/* Tooltip arrow */}
            <div
              className="
                absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1
                w-2 h-2 rotate-45
                bg-white dark:bg-surface-800
                border-l border-b border-white/50 dark:border-surface-700/50
              "
            />
          </div>
        )}
      </Link>
    </li>
  );
}
