/**
 * Authentication Components Index
 *
 * Export all authentication-related components
 */

export { default as LoginPage } from './LoginPage';
export { default as SignUpPage } from './SignUpPage';
export { default as VerifyEmailPage } from './VerifyEmailPage';
export { default as ForgotPasswordPage } from './ForgotPasswordPage';
export { default as ResetPasswordPage } from './ResetPasswordPage';
export { default as AuthLayout } from './AuthLayout';
export { default as ProtectedRoute } from './ProtectedRoute';
export { SessionTimeoutModal } from './ProtectedRoute';

// Re-export form components from AuthLayout
export {
  FormInput,
  FormCheckbox,
  SubmitButton,
  Alert,
  PasswordStrength,
  Divider,
} from './AuthLayout';
