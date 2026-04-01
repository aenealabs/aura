/**
 * Project Aura - Integration Provider Logos
 *
 * Official brand logos for integration providers rendered as SVG components.
 * Each logo includes the brand's official background color.
 */

// Zendesk Logo - Dark teal background
export function ZendeskLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#03363D"/>
      <path d="M12.5 11V21L5 11H12.5Z" fill="white"/>
      <path d="M12.5 8C12.5 10.2091 10.7091 12 8.5 12C6.29086 12 4.5 10.2091 4.5 8H12.5Z" fill="white"/>
      <path d="M14.5 21V11L22 21H14.5Z" fill="white"/>
      <path d="M14.5 8C14.5 10.2091 16.2909 12 18.5 12C20.7091 12 22.5 10.2091 22.5 8H14.5Z" fill="white"/>
    </svg>
  );
}

// Linear Logo - Purple background
export function LinearLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#5E6AD2"/>
      <path d="M6.51472 17.8995C6.18357 17.5683 6.18357 17.0317 6.51472 16.7005L16.7005 6.51472C17.0317 6.18357 17.5683 6.18357 17.8995 6.51472L25.4853 14.1005C25.8164 14.4317 25.8164 14.9683 25.4853 15.2995L15.2995 25.4853C14.9683 25.8164 14.4317 25.8164 14.1005 25.4853L6.51472 17.8995Z" fill="white"/>
    </svg>
  );
}

// ServiceNow Logo - Green/teal background
export function ServiceNowLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#62D84E"/>
      <path d="M16 6C10.4772 6 6 10.4772 6 16C6 21.5228 10.4772 26 16 26C21.5228 26 26 21.5228 26 16C26 10.4772 21.5228 6 16 6ZM16 21C13.2386 21 11 18.7614 11 16C11 13.2386 13.2386 11 16 11C18.7614 11 21 13.2386 21 16C21 18.7614 18.7614 21 16 21Z" fill="white"/>
    </svg>
  );
}

// Jira Logo - Blue background
export function JiraLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#0052CC"/>
      <path d="M24.5 15.5L16.5 7.5L16 7L8 15L15.5 22.5L16 23L16.5 22.5L20 19L16.5 15.5L19.5 12.5L24.5 15.5Z" fill="white"/>
      <path d="M16 18C14.6193 18 13.5 16.8807 13.5 15.5C13.5 14.1193 14.6193 13 16 13L20 17L16 21V18Z" fill="#DEEBFF"/>
      <path d="M16 13C17.3807 13 18.5 14.1193 18.5 15.5C18.5 16.8807 17.3807 18 16 18L12 14L16 10V13Z" fill="#DEEBFF"/>
    </svg>
  );
}

// GitHub Logo - Dark background
export function GitHubLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#24292F"/>
      <path fillRule="evenodd" clipRule="evenodd" d="M16 5C10.48 5 6 9.48 6 15C6 19.42 8.87 23.17 12.84 24.49C13.34 24.58 13.52 24.27 13.52 24C13.52 23.77 13.51 23.14 13.51 22.31C10.73 22.91 10.14 21.16 10.14 21.16C9.68 20.01 9.03 19.7 9.03 19.7C8.12 19.08 9.1 19.1 9.1 19.1C10.1 19.17 10.63 20.14 10.63 20.14C11.5 21.67 12.97 21.23 13.54 20.97C13.63 20.32 13.89 19.88 14.17 19.63C11.95 19.38 9.62 18.5 9.62 14.68C9.62 13.6 10.01 12.72 10.65 12.03C10.55 11.78 10.2 10.77 10.74 9.39C10.74 9.39 11.56 9.12 13.5 10.42C14.29 10.2 15.14 10.09 16 10.09C16.86 10.09 17.71 10.2 18.5 10.42C20.44 9.12 21.26 9.39 21.26 9.39C21.8 10.77 21.45 11.78 21.35 12.03C21.99 12.72 22.38 13.6 22.38 14.68C22.38 18.51 20.04 19.38 17.81 19.63C18.17 19.93 18.5 20.53 18.5 21.45C18.5 22.78 18.48 23.86 18.48 24C18.48 24.27 18.66 24.59 19.17 24.49C23.14 23.17 26 19.42 26 15C26 9.48 21.52 5 16 5Z" fill="white"/>
    </svg>
  );
}

// Datadog Logo - Purple background
export function DatadogLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#632CA6"/>
      <path d="M19.5 9.5L22 11L21 13.5L23.5 15L21.5 17L23 19.5L20 21L18.5 23.5L15.5 22L12.5 24L11 21.5L8 20L9.5 17L7.5 15L10 13L9 10.5L11.5 9L13.5 6.5L16 8L18.5 6L19.5 9.5Z" fill="white"/>
      <ellipse cx="16" cy="14.5" rx="3" ry="3.5" fill="#632CA6"/>
      <circle cx="14.5" cy="13.5" r="1" fill="white"/>
      <circle cx="17.5" cy="13.5" r="1" fill="white"/>
      <path d="M14 16.5C14 16.5 15 17.5 16 17.5C17 17.5 18 16.5 18 16.5" stroke="white" strokeWidth="0.75" strokeLinecap="round"/>
    </svg>
  );
}

// PagerDuty Logo - Green background
export function PagerDutyLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#06AC38"/>
      <path d="M10 7H17C20.3137 7 23 9.68629 23 13C23 16.3137 20.3137 19 17 19H14V25H10V7Z" fill="white"/>
      <path d="M14 10H16.5C17.8807 10 19 11.1193 19 12.5C19 13.8807 17.8807 15 16.5 15H14V10Z" fill="#06AC38"/>
    </svg>
  );
}

// Snyk Logo - Purple/indigo background
export function SnykLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#4C4A73"/>
      <path d="M16 5L6 10V16C6 21.5228 10.4772 26 16 26C21.5228 26 26 21.5228 26 16V10L16 5Z" fill="white"/>
      <path d="M16 9L10 12V16C10 19.3137 12.6863 22 16 22C19.3137 22 22 19.3137 22 16V12L16 9Z" fill="#4C4A73"/>
      <path d="M16 13L13 14.5V16C13 17.6569 14.3431 19 16 19C17.6569 19 19 17.6569 19 16V14.5L16 13Z" fill="white"/>
    </svg>
  );
}

// Qualys Logo - Red background
export function QualysLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#ED2E26"/>
      <path d="M16 6C10.4772 6 6 10.4772 6 16C6 21.5228 10.4772 26 16 26C18.5 26 20.7 25 22.3 23.4L20 21C19 22 17.5 22.5 16 22.5C12.4 22.5 9.5 19.6 9.5 16C9.5 12.4 12.4 9.5 16 9.5C19.6 9.5 22.5 12.4 22.5 16C22.5 17 22.2 17.9 21.8 18.7L24.2 21C25.3 19.5 26 17.8 26 16C26 10.4772 21.5228 6 16 6Z" fill="white"/>
      <path d="M20 24L23 27L26 24L23 21L20 24Z" fill="white"/>
    </svg>
  );
}

// Splunk Logo - Black background with green accent
export function SplunkLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#000000"/>
      <path d="M8 10L16 16L8 22V10Z" fill="#65A637"/>
      <path d="M14 10L22 16L14 22V10Z" fill="white"/>
    </svg>
  );
}

// GitHub Actions Logo - Blue background
export function GitHubActionsLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#2088FF"/>
      <circle cx="16" cy="16" r="8" fill="white" fillOpacity="0.2"/>
      <path d="M13 11L21 16L13 21V11Z" fill="white"/>
    </svg>
  );
}

// Slack Logo - Purple/aubergine background
export function SlackLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#4A154B"/>
      <path d="M10.5 17.5C10.5 18.6046 9.60457 19.5 8.5 19.5C7.39543 19.5 6.5 18.6046 6.5 17.5C6.5 16.3954 7.39543 15.5 8.5 15.5H10.5V17.5Z" fill="#E01E5A"/>
      <path d="M11.5 17.5C11.5 16.3954 12.3954 15.5 13.5 15.5C14.6046 15.5 15.5 16.3954 15.5 17.5V23.5C15.5 24.6046 14.6046 25.5 13.5 25.5C12.3954 25.5 11.5 24.6046 11.5 23.5V17.5Z" fill="#E01E5A"/>
      <path d="M13.5 10.5C12.3954 10.5 11.5 9.60457 11.5 8.5C11.5 7.39543 12.3954 6.5 13.5 6.5C14.6046 6.5 15.5 7.39543 15.5 8.5V10.5H13.5Z" fill="#36C5F0"/>
      <path d="M13.5 11.5C14.6046 11.5 15.5 12.3954 15.5 13.5C15.5 14.6046 14.6046 15.5 13.5 15.5H7.5C6.39543 15.5 5.5 14.6046 5.5 13.5C5.5 12.3954 6.39543 11.5 7.5 11.5H13.5Z" fill="#36C5F0"/>
      <path d="M20.5 13.5C20.5 12.3954 21.3954 11.5 22.5 11.5C23.6046 11.5 24.5 12.3954 24.5 13.5C24.5 14.6046 23.6046 15.5 22.5 15.5H20.5V13.5Z" fill="#2EB67D"/>
      <path d="M19.5 13.5C19.5 14.6046 18.6046 15.5 17.5 15.5C16.3954 15.5 15.5 14.6046 15.5 13.5V7.5C15.5 6.39543 16.3954 5.5 17.5 5.5C18.6046 5.5 19.5 6.39543 19.5 7.5V13.5Z" fill="#2EB67D"/>
      <path d="M17.5 20.5C18.6046 20.5 19.5 21.3954 19.5 22.5C19.5 23.6046 18.6046 24.5 17.5 24.5C16.3954 24.5 15.5 23.6046 15.5 22.5V20.5H17.5Z" fill="#ECB22E"/>
      <path d="M17.5 19.5C16.3954 19.5 15.5 18.6046 15.5 17.5C15.5 16.3954 16.3954 15.5 17.5 15.5H23.5C24.6046 15.5 25.5 16.3954 25.5 17.5C25.5 18.6046 24.6046 19.5 23.5 19.5H17.5Z" fill="#ECB22E"/>
    </svg>
  );
}

// Microsoft Teams Logo - Purple background
export function MicrosoftTeamsLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#5059C9"/>
      <circle cx="21" cy="9" r="2.5" fill="white"/>
      <path d="M24 12H18C17.4477 12 17 12.4477 17 13V20C17 21.6569 18.3431 23 20 23H22C23.6569 23 25 21.6569 25 20V13C25 12.4477 24.5523 12 24 12Z" fill="white" fillOpacity="0.8"/>
      <circle cx="13" cy="8" r="3" fill="white"/>
      <path d="M18 11H8C7.44772 11 7 11.4477 7 12V21C7 23.2091 8.79086 25 11 25H15C17.2091 25 19 23.2091 19 21V12C19 11.4477 18.5523 11 18 11Z" fill="white"/>
      <rect x="9" y="14" width="8" height="2" fill="#5059C9"/>
      <rect x="12" y="14" width="2" height="8" fill="#5059C9"/>
    </svg>
  );
}

// Dataiku Logo - Blue background
export function DataikuLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#2AB1AC"/>
      <path d="M8 16C8 11.5817 11.5817 8 16 8V16H8Z" fill="white"/>
      <path d="M16 16H24C24 20.4183 20.4183 24 16 24V16Z" fill="white"/>
      <circle cx="16" cy="16" r="3" fill="#2AB1AC"/>
    </svg>
  );
}

// Fivetran Logo - Blue background
export function FivetranLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#0073FF"/>
      <path d="M8 10H24V12H8V10Z" fill="white"/>
      <path d="M8 15H20V17H8V15Z" fill="white"/>
      <path d="M8 20H16V22H8V20Z" fill="white"/>
      <circle cx="22" cy="21" r="3" fill="white"/>
    </svg>
  );
}

// VSCode Logo - Blue background
export function VSCodeLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#007ACC"/>
      <path d="M22 7L12 16L22 25V7Z" fill="white" fillOpacity="0.8"/>
      <path d="M10 10L6 13V19L10 22L12 16L10 10Z" fill="white"/>
      <path d="M22 7L12 16L10 10L22 7Z" fill="white" fillOpacity="0.9"/>
      <path d="M22 25L12 16L10 22L22 25Z" fill="white" fillOpacity="0.9"/>
    </svg>
  );
}

// PyCharm Logo - Green/Yellow background
export function PyCharmLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#21D789"/>
      <rect x="7" y="7" width="18" height="18" fill="#000000"/>
      <path d="M10 22H18V24H10V22Z" fill="white"/>
      <path d="M10 10H14C15.6569 10 17 11.3431 17 13C17 14.6569 15.6569 16 14 16H10V10Z" fill="white"/>
      <path d="M10 12H13.5C14.3284 12 15 12.6716 15 13.5C15 14.3284 14.3284 15 13.5 15H10V12Z" fill="#000000"/>
    </svg>
  );
}

// JupyterLab Logo - Orange background
export function JupyterLabLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#F37626"/>
      <ellipse cx="16" cy="16" rx="9" ry="4" stroke="white" strokeWidth="1.5" fill="none"/>
      <ellipse cx="16" cy="16" rx="9" ry="4" stroke="white" strokeWidth="1.5" fill="none" transform="rotate(60 16 16)"/>
      <ellipse cx="16" cy="16" rx="9" ry="4" stroke="white" strokeWidth="1.5" fill="none" transform="rotate(120 16 16)"/>
      <circle cx="16" cy="16" r="2.5" fill="white"/>
      <circle cx="16" cy="9" r="1.5" fill="white"/>
      <circle cx="22" cy="19.5" r="1.5" fill="white"/>
      <circle cx="10" cy="19.5" r="1.5" fill="white"/>
    </svg>
  );
}

// Zscaler Logo - Blue background with zero trust shield
export function ZscalerLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#0090D4"/>
      <path d="M16 5L6 10V16C6 21.5228 10.4772 26 16 26C21.5228 26 26 21.5228 26 16V10L16 5Z" fill="white" fillOpacity="0.2"/>
      <path d="M16 8L9 11.5V16C9 19.866 12.134 23 16 23C19.866 23 23 19.866 23 16V11.5L16 8Z" fill="white"/>
      <path d="M12 15H20L12 19V15Z" fill="#0090D4"/>
      <path d="M12 13H20V15H12V13Z" fill="#0090D4"/>
    </svg>
  );
}

// Saviynt Logo - Indigo/purple background with identity icon
export function SaviyntLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#5C4EE5"/>
      <circle cx="16" cy="11" r="4" fill="white"/>
      <path d="M8 24C8 19.5817 11.5817 16 16 16C20.4183 16 24 19.5817 24 24V25H8V24Z" fill="white"/>
      <circle cx="23" cy="11" r="2.5" fill="white" fillOpacity="0.6"/>
      <path d="M20 19C20 17.3431 21.3431 16 23 16C24.6569 16 26 17.3431 26 19V20H20V19Z" fill="white" fillOpacity="0.6"/>
      <circle cx="9" cy="11" r="2.5" fill="white" fillOpacity="0.6"/>
      <path d="M6 19C6 17.3431 7.34315 16 9 16C10.6569 16 12 17.3431 12 19V20H6V19Z" fill="white" fillOpacity="0.6"/>
    </svg>
  );
}

// AuditBoard Logo - Emerald green background with clipboard/check
export function AuditBoardLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#059669"/>
      <rect x="8" y="6" width="16" height="20" rx="2" fill="white"/>
      <rect x="12" y="4" width="8" height="4" rx="1" fill="white"/>
      <rect x="12" y="4" width="8" height="4" rx="1" stroke="#059669" strokeWidth="1"/>
      <path d="M11 15L14 18L21 11" stroke="#059669" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ============================================================================
// Identity Provider Logos (ADR-054)
// ============================================================================

// Microsoft Active Directory / LDAP Logo - Azure blue background
export function MicrosoftADLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#0078D4"/>
      <rect x="6" y="6" width="9" height="9" fill="#F25022"/>
      <rect x="17" y="6" width="9" height="9" fill="#7FBA00"/>
      <rect x="6" y="17" width="9" height="9" fill="#00A4EF"/>
      <rect x="17" y="17" width="9" height="9" fill="#FFB900"/>
    </svg>
  );
}

// Okta Logo (for SAML 2.0) - Blue background
export function OktaLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#007DC1"/>
      <circle cx="16" cy="16" r="8" fill="white"/>
      <circle cx="16" cy="16" r="4" fill="#007DC1"/>
    </svg>
  );
}

// OpenID Connect Logo - Orange/red gradient feel
export function OpenIDLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#F78C40"/>
      <path d="M16 7L16 19" stroke="white" strokeWidth="3" strokeLinecap="round"/>
      <path d="M16 19L16 25" stroke="#B3B3B3" strokeWidth="3" strokeLinecap="round"/>
      <circle cx="16" cy="13" r="6" stroke="white" strokeWidth="2.5" fill="none"/>
      <path d="M21 21L26 26" stroke="white" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

// Ping Identity Logo - Red/maroon background
export function PingIdentityLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#B91C1C"/>
      <circle cx="16" cy="12" r="5" fill="white"/>
      <path d="M8 26C8 21.0294 11.5817 17 16 17C20.4183 17 24 21.0294 24 26" stroke="white" strokeWidth="3" strokeLinecap="round"/>
      <circle cx="16" cy="12" r="2" fill="#B91C1C"/>
    </svg>
  );
}

// AWS Cognito Logo - AWS Orange background
export function AWSCognitoLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#DD344C"/>
      <circle cx="16" cy="11" r="4" fill="white"/>
      <path d="M9 24C9 20.134 12.134 17 16 17C19.866 17 23 20.134 23 24V25H9V24Z" fill="white"/>
      <path d="M16 6L18 8.5L16 11L14 8.5L16 6Z" fill="white" fillOpacity="0.6"/>
      <circle cx="22" cy="14" r="2" fill="white" fillOpacity="0.6"/>
      <circle cx="10" cy="14" r="2" fill="white" fillOpacity="0.6"/>
    </svg>
  );
}

// Auth0 Logo (alternative for OIDC) - Black background
export function Auth0Logo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#000000"/>
      <path d="M16 6L21 11.5L19 17L16 14L13 17L11 11.5L16 6Z" fill="#EB5424"/>
      <path d="M11 11.5L6 17L11 22.5L13 17L11 11.5Z" fill="#EB5424"/>
      <path d="M21 11.5L26 17L21 22.5L19 17L21 11.5Z" fill="#EB5424"/>
      <path d="M11 22.5L16 17L21 22.5L16 28L11 22.5Z" fill="#EB5424"/>
    </svg>
  );
}

// Google Logo (alternative for OIDC) - White background with Google colors
export function GoogleLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#FFFFFF"/>
      <rect x="0.5" y="0.5" width="31" height="31" rx="5.5" stroke="#E5E7EB"/>
      <path d="M23.7 16.2C23.7 15.6 23.65 15.1 23.55 14.6H16V17.6H20.3C20.1 18.6 19.55 19.45 18.7 20V22.1H21.3C22.8 20.7 23.7 18.65 23.7 16.2Z" fill="#4285F4"/>
      <path d="M16 24C18.15 24 19.95 23.3 21.3 22.1L18.7 20C17.95 20.5 17.05 20.8 16 20.8C13.95 20.8 12.2 19.35 11.55 17.45H8.85V19.6C10.2 22.3 12.9 24 16 24Z" fill="#34A853"/>
      <path d="M11.55 17.45C11.4 17 11.3 16.5 11.3 16C11.3 15.5 11.4 15 11.55 14.55V12.4H8.85C8.3 13.5 8 14.7 8 16C8 17.3 8.3 18.5 8.85 19.6L11.55 17.45Z" fill="#FBBC05"/>
      <path d="M16 11.2C17.15 11.2 18.2 11.6 19.05 12.4L21.35 10.1C19.95 8.8 18.15 8 16 8C12.9 8 10.2 9.7 8.85 12.4L11.55 14.55C12.2 12.65 13.95 11.2 16 11.2Z" fill="#EA4335"/>
    </svg>
  );
}

// Microsoft Entra ID Logo (formerly Azure AD) - Azure blue with Entra gradient
export function EntraIDLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#0078D4"/>
      <defs>
        <linearGradient id="entraGrad" x1="8" y1="8" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop stopColor="#50E6FF"/>
          <stop offset="1" stopColor="#0078D4"/>
        </linearGradient>
      </defs>
      <circle cx="16" cy="12" r="5" fill="white"/>
      <path d="M8 25C8 20.0294 11.5817 16 16 16C20.4183 16 24 20.0294 24 25" stroke="white" strokeWidth="3" strokeLinecap="round"/>
      <path d="M21 9L25 5M25 5L25 8M25 5L22 5" stroke="url(#entraGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// Azure AD B2C Logo - Azure blue with B2C customer icon
export function AzureADB2CLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#00BCF2"/>
      <circle cx="12" cy="11" r="3.5" fill="white"/>
      <path d="M6 21C6 17.6863 8.68629 15 12 15C15.3137 15 18 17.6863 18 21V22H6V21Z" fill="white"/>
      <circle cx="21" cy="13" r="2.5" fill="white" fillOpacity="0.7"/>
      <path d="M17 22C17 19.7909 18.7909 18 21 18C23.2091 18 25 19.7909 25 22V23H17V22Z" fill="white" fillOpacity="0.7"/>
      <circle cx="21" cy="8" r="2" fill="white" fillOpacity="0.5"/>
      <path d="M18 13C18 11.3431 19.3431 10 21 10C22.6569 10 24 11.3431 24 13" stroke="white" strokeOpacity="0.5" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

// Palantir AIP Logo - Black background with geometric hexagon (ADR-074/075)
export function PalantirLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#101820"/>
      <path d="M16 6L24 10.5V19.5L16 24L8 19.5V10.5L16 6Z" stroke="white" strokeWidth="1.5" fill="none"/>
      <path d="M16 10L20 12.5V17.5L16 20L12 17.5V12.5L16 10Z" fill="white"/>
      <path d="M16 6V10M16 20V24M8 10.5L12 12.5M20 17.5L24 19.5M24 10.5L20 12.5M12 17.5L8 19.5" stroke="white" strokeWidth="1" strokeOpacity="0.5"/>
    </svg>
  );
}

// Default/Fallback Logo - Gray background
export function DefaultProviderLogo({ className = 'w-8 h-8' }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="6" fill="#6B7280"/>
      <path d="M11 16H21M16 11V21" stroke="white" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

/**
 * Provider logo mapping
 * Maps provider IDs to their respective logo components
 */
export const PROVIDER_LOGOS = {
  zendesk: ZendeskLogo,
  linear: LinearLogo,
  servicenow: ServiceNowLogo,
  jira: JiraLogo,
  github_issues: GitHubLogo,
  datadog: DatadogLogo,
  pagerduty: PagerDutyLogo,
  splunk: SplunkLogo,
  snyk: SnykLogo,
  qualys: QualysLogo,
  github_actions: GitHubActionsLogo,
  slack: SlackLogo,
  microsoft_teams: MicrosoftTeamsLogo,
  dataiku: DataikuLogo,
  fivetran: FivetranLogo,
  vscode: VSCodeLogo,
  pycharm: PyCharmLogo,
  jupyterlab: JupyterLabLogo,
  // ADR-074/075 Palantir AIP Integration
  palantir_aip: PalantirLogo,
  palantir: PalantirLogo,
  // ADR-053 Enterprise Security Integrations
  zscaler: ZscalerLogo,
  saviynt: SaviyntLogo,
  auditboard: AuditBoardLogo,
  // ADR-054 Identity Provider Logos
  ldap: MicrosoftADLogo,
  active_directory: MicrosoftADLogo,
  microsoft_ad: MicrosoftADLogo,
  saml: OktaLogo,
  okta: OktaLogo,
  oidc: OpenIDLogo,
  openid: OpenIDLogo,
  auth0: Auth0Logo,
  google: GoogleLogo,
  pingid: PingIdentityLogo,
  ping_identity: PingIdentityLogo,
  cognito: AWSCognitoLogo,
  aws_cognito: AWSCognitoLogo,
  // Azure Identity Providers
  entra_id: EntraIDLogo,
  azure_ad: EntraIDLogo,
  microsoft_entra: EntraIDLogo,
  azure_ad_b2c: AzureADB2CLogo,
  entra_b2c: AzureADB2CLogo,
};

/**
 * Get logo component for a provider
 * @param {string} providerId - Provider identifier
 * @returns {React.Component} Logo component
 */
export function getProviderLogo(providerId) {
  return PROVIDER_LOGOS[providerId] || DefaultProviderLogo;
}

export default PROVIDER_LOGOS;
