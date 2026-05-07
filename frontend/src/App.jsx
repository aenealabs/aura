import { lazy } from 'react';
import { BrowserRouter, Routes, Route, Outlet, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ChatProvider } from './context/ChatContext';
import { SecurityAlertsProvider } from './context/SecurityAlertsContext';
import { RepositoryProvider } from './context/RepositoryContext';
import { OnboardingProvider } from './context/OnboardingContext';
import { EditionProvider } from './context/EditionContext';
import { DeveloperModeProvider } from './context/DeveloperModeContext';
import CollapsibleSidebar from './components/CollapsibleSidebar';
import ChatAssistant from './components/chat/ChatAssistant';
import LicenseExpirationBanner from './components/LicenseExpirationBanner';
import { PerformanceBar, APIInspectorDrawer } from './components/developer';
import { CommandPaletteProvider } from './components/CommandPalette';
import { ErrorBoundary } from './components/ui/ErrorBoundary';
import { ToastProvider } from './components/ui/Toast';
import { ConfirmProvider } from './components/ui/ConfirmDialog';
import { SuspenseWrapper } from './components/ui/PageLoadingFallback';
import { useErrorTracking, useEngagementTracking } from './hooks/useErrorTracking';
import {
  WelcomeModal,
  OnboardingChecklist,
  WelcomeTour,
  DevToolbar,
} from './components/onboarding';

// Lazy load all page components for code splitting
const Dashboard = lazy(() => import('./components/Dashboard'));
const CKGEConsole = lazy(() => import('./components/CKGEConsole'));
const ActivityDetail = lazy(() => import('./components/ActivityDetail'));
const ApprovalDashboard = lazy(() => import('./components/ApprovalDashboard'));
const ModelAssuranceQueue = lazy(() =>
  import('./components/modelAssurance/ModelAssuranceQueue'),
);
const IncidentInvestigations = lazy(() => import('./components/IncidentInvestigations'));
const SecurityAlertsPanel = lazy(() => import('./components/SecurityAlertsPanel'));
const SettingsPage = lazy(() => import('./components/SettingsPage'));
const ProfilePage = lazy(() => import('./components/ProfilePage'));
const RedTeamDashboard = lazy(() => import('./components/RedTeamDashboard'));
const AgentRegistry = lazy(() => import('./components/AgentRegistry'));
const AgentManagerView = lazy(() => import('./components/AgentManagerView'));
const Environments = lazy(() => import('./components/Environments'));
const AuthCallback = lazy(() => import('./components/AuthCallback'));

// Lazy load barrel exports with explicit default extraction
const IntegrationHub = lazy(() =>
  import('./components/integrations').then((m) => ({ default: m.IntegrationHub }))
);
const RepositoriesList = lazy(() =>
  import('./components/repositories').then((m) => ({ default: m.RepositoriesList }))
);
const TraceExplorer = lazy(() =>
  import('./components/observability').then((m) => ({ default: m.TraceExplorer }))
);
const SchedulingPage = lazy(() =>
  import('./components/scheduling').then((m) => ({ default: m.SchedulingPage }))
);
const DocumentationDashboard = lazy(() =>
  import('./components/documentation').then((m) => ({ default: m.DocumentationDashboard }))
);
const EnvValidatorDashboard = lazy(() =>
  import('./components/EnvValidator').then((m) => ({ default: m.EnvValidatorDashboard }))
);
const TrustCenterPage = lazy(() =>
  import('./components/trustcenter').then((m) => ({ default: m.TrustCenterPage }))
);
const GuardrailSettingsPage = lazy(() =>
  import('./components/guardrails').then((m) => ({ default: m.GuardrailSettingsPage }))
);
const ExplainabilityPage = lazy(() =>
  import('./components/explainability').then((m) => ({ default: m.ExplainabilityPage }))
);
const CapabilityGraphPage = lazy(() =>
  import('./components/capability').then((m) => ({ default: m.CapabilityGraphPage }))
);
const ScannerDashboardPage = lazy(() =>
  import('./components/scanner').then((m) => ({ default: m.ScanDetailPage }))
);

// Lazy load auth pages (infrequently accessed after login)
const LoginPage = lazy(() =>
  import('./components/auth').then((m) => ({ default: m.LoginPage }))
);
const SignUpPage = lazy(() =>
  import('./components/auth').then((m) => ({ default: m.SignUpPage }))
);
const VerifyEmailPage = lazy(() =>
  import('./components/auth').then((m) => ({ default: m.VerifyEmailPage }))
);
const ForgotPasswordPage = lazy(() =>
  import('./components/auth').then((m) => ({ default: m.ForgotPasswordPage }))
);
const ResetPasswordPage = lazy(() =>
  import('./components/auth').then((m) => ({ default: m.ResetPasswordPage }))
);

// ProtectedRoute is kept static as it's part of the critical auth path
import { ProtectedRoute } from './components/auth';

/**
 * Error Tracking Initializer Component
 * Must be inside BrowserRouter for route tracking to work
 */
function ErrorTrackingInitializer({ children }) {
  const { user } = useAuth();

  // Initialize error tracking with user context and route tracking
  useErrorTracking({
    user,
    enablePerformance: true,
    trackRoutes: true,
  });

  // Track user engagement (page visibility, time on page)
  useEngagementTracking();

  return children;
}

/**
 * Skip Links Component - WCAG 2.1 AA Keyboard Navigation
 * Allows keyboard users to skip navigation and jump to main content
 */
const SkipLinks = () => (
  <div className="skip-links">
    <a
      href="#main-content"
      className="
        sr-only focus:not-sr-only
        fixed top-4 left-4 z-[200]
        px-4 py-2 bg-aura-600 text-white font-medium
        rounded-lg shadow-lg
        focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
        transition-all duration-200
      "
    >
      Skip to main content
    </a>
    <a
      href="#navigation"
      className="
        sr-only focus:not-sr-only
        fixed top-4 left-48 z-[200]
        px-4 py-2 bg-aura-600 text-white font-medium
        rounded-lg shadow-lg
        focus:outline-none focus:ring-2 focus:ring-aura-500 focus:ring-offset-2
        transition-all duration-200
      "
    >
      Skip to navigation
    </a>
  </div>
);

// Main layout with persistent sidebar (for authenticated users)
const AppLayout = () => (
  <DeveloperModeProvider>
    <EditionProvider>
      <OnboardingProvider>
        <div className="flex flex-col h-screen bg-surface-50 dark:bg-surface-900 font-sans transition-colors duration-300">
          {/* Skip Links for WCAG 2.1 AA Keyboard Navigation */}
          <SkipLinks />
          {/* License Expiration Banner (shown at top of app when license is expiring) */}
          <LicenseExpirationBanner />
          <div className="flex flex-1 overflow-hidden">
            <CollapsibleSidebar />
            <main id="main-content" className="flex-1 flex flex-col overflow-hidden bg-grid-dot" tabIndex="-1">
              <Outlet />
            </main>
          </div>
          {/* Aura Assistant - AI-powered chat interface */}
          <ChatAssistant />
          {/* Onboarding Components */}
          <WelcomeModal />
          <OnboardingChecklist />
          <WelcomeTour />
          {/* Dev Toolbar (only visible in development mode) */}
          <DevToolbar />
          {/* Developer Tools (only visible when dev mode is enabled) */}
          <PerformanceBar />
          <APIInspectorDrawer />
        </div>
      </OnboardingProvider>
    </EditionProvider>
  </DeveloperModeProvider>
);

// Protected layout wrapper
const ProtectedLayout = () => (
  <ProtectedRoute>
    <AppLayout />
  </ProtectedRoute>
);

export default function App() {
  return (
    <ErrorBoundary
      name="RootErrorBoundary"
      variant="fullPage"
      errorTitle="Application Error"
      errorMessage="We're sorry, but something went wrong. Our team has been notified and is working to fix this issue."
    >
      <ThemeProvider>
        <AuthProvider>
          <ChatProvider>
            <SecurityAlertsProvider>
              <RepositoryProvider>
                <BrowserRouter>
                  <ErrorTrackingInitializer>
                    <ConfirmProvider>
                    <ToastProvider>
                      <CommandPaletteProvider>
                        <Routes>
                        {/* Public authentication routes */}
                        <Route
                          path="/login"
                          element={
                            <SuspenseWrapper name="Login">
                              <LoginPage />
                            </SuspenseWrapper>
                          }
                        />
                        <Route
                          path="/signup"
                          element={
                            <SuspenseWrapper name="Sign Up">
                              <SignUpPage />
                            </SuspenseWrapper>
                          }
                        />
                        <Route
                          path="/verify-email"
                          element={
                            <SuspenseWrapper name="Email Verification">
                              <VerifyEmailPage />
                            </SuspenseWrapper>
                          }
                        />
                        <Route
                          path="/forgot-password"
                          element={
                            <SuspenseWrapper name="Password Recovery">
                              <ForgotPasswordPage />
                            </SuspenseWrapper>
                          }
                        />
                        <Route
                          path="/reset-password"
                          element={
                            <SuspenseWrapper name="Password Reset">
                              <ResetPasswordPage />
                            </SuspenseWrapper>
                          }
                        />
                        <Route
                          path="/auth/callback"
                          element={
                            <SuspenseWrapper name="Authentication">
                              <AuthCallback />
                            </SuspenseWrapper>
                          }
                        />

                        {/* Protected routes */}
                        <Route element={<ProtectedLayout />}>
                          <Route
                            index
                            element={
                              <SuspenseWrapper name="Dashboard">
                                <Dashboard />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/graph"
                            element={
                              <SuspenseWrapper name="Knowledge Graph">
                                <CKGEConsole />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/repositories"
                            element={
                              <SuspenseWrapper name="Repositories">
                                <RepositoriesList />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/sandboxes"
                            element={
                              <SuspenseWrapper name="Sandboxes">
                                <Environments />
                              </SuspenseWrapper>
                            }
                          />
                          {/* Redirect old /environments route to /sandboxes */}
                          <Route
                            path="/environments"
                            element={<Navigate to="/sandboxes" replace />}
                          />
                          <Route
                            path="/approvals"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Approvals">
                                  <ApprovalDashboard />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/model-assurance"
                            element={
                              <ProtectedRoute requiredRole={['admin']}>
                                <SuspenseWrapper name="ModelAssurance">
                                  <ModelAssuranceQueue />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/incidents"
                            element={
                              <SuspenseWrapper name="Incidents">
                                <IncidentInvestigations />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/security/red-team"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Red Team">
                                  <RedTeamDashboard />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/security/scanner"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Vulnerability Scanner">
                                  <ScannerDashboardPage />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/security/alerts"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Security Alerts">
                                  <SecurityAlertsPanel />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/validator"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Environment Validator">
                                  <EnvValidatorDashboard />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/trust-center"
                            element={
                              <SuspenseWrapper name="AI Trust Center">
                                <TrustCenterPage />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/guardrails"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Guardrail Settings">
                                  <GuardrailSettingsPage />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/explainability"
                            element={
                              <SuspenseWrapper name="Explainability Dashboard">
                                <ExplainabilityPage />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/capability-graph"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Capability Graph">
                                  <CapabilityGraphPage />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/settings"
                            element={
                              <SuspenseWrapper name="Settings">
                                <SettingsPage />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/profile"
                            element={
                              <SuspenseWrapper name="Profile">
                                <ProfilePage />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/integrations"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Integrations">
                                  <IntegrationHub />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/agents/registry"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer']}>
                                <SuspenseWrapper name="Agent Registry">
                                  <AgentRegistry />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/agents/mission-control"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer', 'developer']}>
                                <SuspenseWrapper name="Mission Control">
                                  <AgentManagerView />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/agents/mission-control/:agentId"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer', 'developer']}>
                                <SuspenseWrapper name="Mission Control">
                                  <AgentManagerView />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/agents/scheduling"
                            element={
                              <ProtectedRoute requiredRole={['admin', 'security-engineer', 'developer']}>
                                <SuspenseWrapper name="Agent Scheduling">
                                  <SchedulingPage />
                                </SuspenseWrapper>
                              </ProtectedRoute>
                            }
                          />
                          <Route
                            path="/observability/traces"
                            element={
                              <SuspenseWrapper name="Trace Explorer">
                                <TraceExplorer />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/documentation"
                            element={
                              <SuspenseWrapper name="Documentation">
                                <DocumentationDashboard />
                              </SuspenseWrapper>
                            }
                          />
                          <Route
                            path="/activity/:activityId"
                            element={
                              <SuspenseWrapper name="Activity Details">
                                <ActivityDetail />
                              </SuspenseWrapper>
                            }
                          />
                        </Route>
                        </Routes>
                      </CommandPaletteProvider>
                    </ToastProvider>
                    </ConfirmProvider>
                  </ErrorTrackingInitializer>
                </BrowserRouter>
              </RepositoryProvider>
            </SecurityAlertsProvider>
          </ChatProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
