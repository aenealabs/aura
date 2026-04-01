#!/bin/bash
# =============================================================================
# Project Aura - Interactive Configuration Wizard
# =============================================================================
# Guides users through configuring their Aura deployment with sensible defaults
# and validation for common mistakes.
#
# Usage:
#   ./config-wizard.sh
#   ./config-wizard.sh --output my-config.yaml
#
# Exit Codes:
#   0: Configuration saved successfully
#   1: User cancelled
#   2: Validation failed
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration and Constants
# =============================================================================
readonly VERSION="1.0.0"
readonly DEFAULT_OUTPUT="aura-config.yaml"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly NC='\033[0m'

# Configuration values
OUTPUT_FILE="$DEFAULT_OUTPUT"
CONFIG_PROJECT_NAME=""
CONFIG_ENVIRONMENT=""
CONFIG_REGION=""
CONFIG_SIZE=""
CONFIG_VPC_CIDR=""
CONFIG_DOMAIN=""
CONFIG_CERTIFICATE_ARN=""
CONFIG_BEDROCK_MODELS=""
CONFIG_NEPTUNE_INSTANCE=""
CONFIG_OPENSEARCH_INSTANCE=""
CONFIG_EKS_INSTANCE=""
CONFIG_EKS_MIN_NODES=""
CONFIG_EKS_MAX_NODES=""
CONFIG_ENABLE_GOVCLOUD=""
CONFIG_ENABLE_FIPS=""

# =============================================================================
# Utility Functions
# =============================================================================

print_banner() {
    clear
    cat << 'EOF'

    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║       █████╗ ██╗   ██╗██████╗  █████╗                        ║
    ║      ██╔══██╗██║   ██║██╔══██╗██╔══██╗                       ║
    ║      ███████║██║   ██║██████╔╝███████║                       ║
    ║      ██╔══██║██║   ██║██╔══██╗██╔══██║                       ║
    ║      ██║  ██║╚██████╔╝██║  ██║██║  ██║                       ║
    ║      ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝                       ║
    ║                                                               ║
    ║           Configuration Wizard                                ║
    ║                    by Aenea Labs                              ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝

EOF
    echo -e "    ${CYAN}Version: ${VERSION}${NC}"
    echo ""
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_help_text() {
    echo -e "  ${DIM}$1${NC}"
}

prompt_text() {
    local prompt=$1
    local default=${2:-""}
    local var_name=$3
    local required=${4:-false}

    echo ""
    echo -e "  ${BOLD}$prompt${NC}"
    if [[ -n "$default" ]]; then
        echo -e "  ${DIM}Default: $default${NC}"
    fi
    echo -n "  > "

    local value
    read -r value

    if [[ -z "$value" && -n "$default" ]]; then
        value="$default"
    fi

    if [[ -z "$value" && "$required" == true ]]; then
        log_error "This field is required"
        prompt_text "$prompt" "$default" "$var_name" "$required"
        return
    fi

    eval "$var_name=\"$value\""
}

prompt_select() {
    local prompt=$1
    local var_name=$2
    shift 2
    local options=("$@")

    echo ""
    echo -e "  ${BOLD}$prompt${NC}"
    echo ""

    local i=1
    for opt in "${options[@]}"; do
        echo -e "    ${CYAN}$i)${NC} $opt"
        ((i++))
    done

    echo ""
    echo -n "  Enter choice [1-${#options[@]}]: "

    local choice
    read -r choice

    if [[ ! "$choice" =~ ^[0-9]+$ ]] || [[ "$choice" -lt 1 ]] || [[ "$choice" -gt ${#options[@]} ]]; then
        log_error "Invalid choice. Please enter a number between 1 and ${#options[@]}"
        prompt_select "$prompt" "$var_name" "${options[@]}"
        return
    fi

    local selected="${options[$((choice-1))]}"
    # Extract just the key if format is "key - description"
    selected="${selected%% -*}"
    eval "$var_name=\"$selected\""
}

prompt_yes_no() {
    local prompt=$1
    local default=${2:-"n"}
    local var_name=$3

    echo ""
    echo -e "  ${BOLD}$prompt${NC}"
    if [[ "$default" == "y" ]]; then
        echo -n "  [Y/n]: "
    else
        echo -n "  [y/N]: "
    fi

    local response
    read -r response

    if [[ -z "$response" ]]; then
        response="$default"
    fi

    if [[ "$response" =~ ^[Yy] ]]; then
        eval "$var_name=true"
    else
        eval "$var_name=false"
    fi
}

validate_cidr() {
    local cidr=$1
    if [[ ! "$cidr" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$ ]]; then
        return 1
    fi
    return 0
}

validate_domain() {
    local domain=$1
    if [[ ! "$domain" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$ ]]; then
        return 1
    fi
    return 0
}

# =============================================================================
# Wizard Sections
# =============================================================================

section_basic() {
    print_section "Basic Configuration"

    print_help_text "The project name is used as a prefix for all AWS resources."
    print_help_text "Use lowercase letters, numbers, and hyphens only."
    prompt_text "Project Name" "aura" "CONFIG_PROJECT_NAME" true

    # Validate project name
    if [[ ! "$CONFIG_PROJECT_NAME" =~ ^[a-z][a-z0-9-]*$ ]]; then
        log_error "Project name must start with a letter and contain only lowercase letters, numbers, and hyphens"
        section_basic
        return
    fi

    print_help_text "The environment determines deployment configuration and resource sizing."
    prompt_select "Deployment Environment" "CONFIG_ENVIRONMENT" \
        "dev - Development (minimal resources, no HA)" \
        "qa - Quality Assurance (moderate resources)" \
        "prod - Production (full HA, recommended for customers)"

    echo ""
    log_success "Basic configuration complete"
}

section_aws_region() {
    print_section "AWS Region"

    print_help_text "Choose the AWS region for deployment."
    print_help_text "For GovCloud, select a us-gov region."
    prompt_select "AWS Region" "CONFIG_REGION" \
        "us-east-1 - N. Virginia (recommended)" \
        "us-west-2 - Oregon" \
        "eu-west-1 - Ireland" \
        "eu-central-1 - Frankfurt" \
        "ap-northeast-1 - Tokyo" \
        "us-gov-west-1 - GovCloud West (FedRAMP High)"

    # Check if GovCloud
    if [[ "$CONFIG_REGION" =~ ^us-gov ]]; then
        CONFIG_ENABLE_GOVCLOUD=true
        log_info "GovCloud region detected. Enabling GovCloud-specific settings."

        print_help_text "FIPS 140-2 validated cryptography is required for some compliance frameworks."
        prompt_yes_no "Enable FIPS 140-2 endpoints?" "y" "CONFIG_ENABLE_FIPS"
    else
        CONFIG_ENABLE_GOVCLOUD=false
        CONFIG_ENABLE_FIPS=false
    fi

    echo ""
    log_success "Region configuration complete"
}

section_sizing() {
    print_section "Deployment Size"

    echo -e "  ${BOLD}Choose a deployment size based on your team:${NC}"
    echo ""
    echo -e "  ${CYAN}Small${NC}     1-50 developers"
    echo -e "            ~\$400/month AWS cost"
    echo -e "            t3.medium instances"
    echo ""
    echo -e "  ${CYAN}Medium${NC}    50-200 developers"
    echo -e "            ~\$1,200/month AWS cost"
    echo -e "            r6i.large instances"
    echo ""
    echo -e "  ${CYAN}Enterprise${NC}  200+ developers"
    echo -e "            ~\$3,000/month AWS cost"
    echo -e "            r6i.xlarge instances, multi-AZ"
    echo ""

    prompt_select "Deployment Size" "CONFIG_SIZE" \
        "small - 1-50 developers" \
        "medium - 50-200 developers" \
        "enterprise - 200+ developers"

    # Set defaults based on size
    case "$CONFIG_SIZE" in
        small)
            CONFIG_NEPTUNE_INSTANCE="db.t3.medium"
            CONFIG_OPENSEARCH_INSTANCE="t3.small.search"
            CONFIG_EKS_INSTANCE="t3.medium"
            CONFIG_EKS_MIN_NODES="2"
            CONFIG_EKS_MAX_NODES="4"
            ;;
        medium)
            CONFIG_NEPTUNE_INSTANCE="db.r6g.large"
            CONFIG_OPENSEARCH_INSTANCE="r6g.large.search"
            CONFIG_EKS_INSTANCE="r6i.large"
            CONFIG_EKS_MIN_NODES="3"
            CONFIG_EKS_MAX_NODES="8"
            ;;
        enterprise)
            CONFIG_NEPTUNE_INSTANCE="db.r6g.xlarge"
            CONFIG_OPENSEARCH_INSTANCE="r6g.xlarge.search"
            CONFIG_EKS_INSTANCE="r6i.xlarge"
            CONFIG_EKS_MIN_NODES="6"
            CONFIG_EKS_MAX_NODES="20"
            ;;
    esac

    echo ""
    log_success "Size configuration complete"
}

section_network() {
    print_section "Network Configuration"

    print_help_text "The VPC CIDR block defines the IP address range for your Aura network."
    print_help_text "Use a /16 or larger block that doesn't overlap with existing VPCs."
    prompt_text "VPC CIDR Block" "10.0.0.0/16" "CONFIG_VPC_CIDR"

    # Validate CIDR
    if ! validate_cidr "$CONFIG_VPC_CIDR"; then
        log_error "Invalid CIDR format. Expected format: 10.x.x.x/16"
        section_network
        return
    fi

    echo ""
    log_success "Network configuration complete"
}

section_dns() {
    print_section "DNS and Certificate Configuration"

    print_help_text "Optional: Provide a custom domain for the Aura dashboard."
    print_help_text "Leave blank to use the default ALB endpoint."
    prompt_text "Custom Domain (optional)" "" "CONFIG_DOMAIN"

    if [[ -n "$CONFIG_DOMAIN" ]]; then
        if ! validate_domain "$CONFIG_DOMAIN"; then
            log_error "Invalid domain format"
            section_dns
            return
        fi

        print_help_text "Provide an ACM certificate ARN for HTTPS."
        print_help_text "The certificate must be in the same region as the deployment."
        prompt_text "ACM Certificate ARN" "" "CONFIG_CERTIFICATE_ARN"
    fi

    echo ""
    log_success "DNS configuration complete"
}

section_bedrock() {
    print_section "Bedrock AI Models"

    print_help_text "Aura uses Amazon Bedrock for AI capabilities."
    print_help_text "The following models will be used (ensure you have access):"
    echo ""
    echo -e "  ${CYAN}Required:${NC}"
    echo "    - anthropic.claude-3-5-sonnet-20241022-v1:0 (primary reasoning)"
    echo "    - anthropic.claude-3-haiku-20240307-v1:0 (fast tasks)"
    echo "    - amazon.titan-embed-text-v2:0 (embeddings)"
    echo ""

    prompt_yes_no "Have you requested access to these models in Bedrock?" "n" "bedrock_access"

    if [[ "$bedrock_access" != true ]]; then
        echo ""
        log_warn "Please request model access before deployment:"
        echo "  https://console.aws.amazon.com/bedrock/home#/modelaccess"
        echo ""
        echo "  Press Enter to continue..."
        read -r
    fi

    CONFIG_BEDROCK_MODELS="anthropic.claude-3-5-sonnet-20241022-v1:0,anthropic.claude-3-haiku-20240307-v1:0,amazon.titan-embed-text-v2:0"

    echo ""
    log_success "Bedrock configuration complete"
}

section_advanced() {
    print_section "Advanced Configuration"

    prompt_yes_no "Would you like to customize instance types?" "n" "customize_instances"

    if [[ "$customize_instances" == true ]]; then
        echo ""
        print_help_text "Neptune Instance Type (graph database)"
        prompt_text "Neptune Instance" "$CONFIG_NEPTUNE_INSTANCE" "CONFIG_NEPTUNE_INSTANCE"

        print_help_text "OpenSearch Instance Type (vector search)"
        prompt_text "OpenSearch Instance" "$CONFIG_OPENSEARCH_INSTANCE" "CONFIG_OPENSEARCH_INSTANCE"

        print_help_text "EKS Node Instance Type"
        prompt_text "EKS Instance" "$CONFIG_EKS_INSTANCE" "CONFIG_EKS_INSTANCE"

        print_help_text "EKS Node Group Size"
        prompt_text "Minimum Nodes" "$CONFIG_EKS_MIN_NODES" "CONFIG_EKS_MIN_NODES"
        prompt_text "Maximum Nodes" "$CONFIG_EKS_MAX_NODES" "CONFIG_EKS_MAX_NODES"
    fi

    echo ""
    log_success "Advanced configuration complete"
}

# =============================================================================
# Summary and Output
# =============================================================================

show_summary() {
    print_section "Configuration Summary"

    echo -e "  ${BOLD}Basic Settings${NC}"
    echo "    Project Name:       $CONFIG_PROJECT_NAME"
    echo "    Environment:        $CONFIG_ENVIRONMENT"
    echo "    Deployment Size:    $CONFIG_SIZE"
    echo ""

    echo -e "  ${BOLD}AWS Settings${NC}"
    echo "    Region:             $CONFIG_REGION"
    echo "    GovCloud:           $CONFIG_ENABLE_GOVCLOUD"
    echo "    FIPS Enabled:       $CONFIG_ENABLE_FIPS"
    echo ""

    echo -e "  ${BOLD}Network Settings${NC}"
    echo "    VPC CIDR:           $CONFIG_VPC_CIDR"
    if [[ -n "$CONFIG_DOMAIN" ]]; then
        echo "    Custom Domain:      $CONFIG_DOMAIN"
        echo "    Certificate ARN:    $CONFIG_CERTIFICATE_ARN"
    fi
    echo ""

    echo -e "  ${BOLD}Resource Settings${NC}"
    echo "    Neptune Instance:   $CONFIG_NEPTUNE_INSTANCE"
    echo "    OpenSearch Instance: $CONFIG_OPENSEARCH_INSTANCE"
    echo "    EKS Instance:       $CONFIG_EKS_INSTANCE"
    echo "    EKS Nodes:          $CONFIG_EKS_MIN_NODES - $CONFIG_EKS_MAX_NODES"
    echo ""
}

save_configuration() {
    cat > "$OUTPUT_FILE" << EOF
# =============================================================================
# Project Aura Configuration
# Generated by config-wizard.sh on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# =============================================================================

# Basic Settings
project_name: "$CONFIG_PROJECT_NAME"
environment: "$CONFIG_ENVIRONMENT"
size: "$CONFIG_SIZE"

# AWS Settings
region: "$CONFIG_REGION"
govcloud_enabled: $CONFIG_ENABLE_GOVCLOUD
fips_enabled: $CONFIG_ENABLE_FIPS

# Network Settings
vpc_cidr: "$CONFIG_VPC_CIDR"
domain: "$CONFIG_DOMAIN"
certificate_arn: "$CONFIG_CERTIFICATE_ARN"

# Database Settings
neptune:
  instance_type: "$CONFIG_NEPTUNE_INSTANCE"
  mode: provisioned  # GovCloud compatible

opensearch:
  instance_type: "$CONFIG_OPENSEARCH_INSTANCE"
  volume_size: $([ "$CONFIG_SIZE" == "enterprise" ] && echo "100" || echo "20")

# Compute Settings
eks:
  instance_type: "$CONFIG_EKS_INSTANCE"
  min_nodes: $CONFIG_EKS_MIN_NODES
  max_nodes: $CONFIG_EKS_MAX_NODES
  kubernetes_version: "1.34"

# Bedrock Settings
bedrock:
  models:
    - "anthropic.claude-3-5-sonnet-20241022-v1:0"
    - "anthropic.claude-3-haiku-20240307-v1:0"
    - "amazon.titan-embed-text-v2:0"

# Estimated Monthly Costs (approximate, before Bedrock usage)
# - Small:      ~\$400/month
# - Medium:     ~\$1,200/month
# - Enterprise: ~\$3,000/month

# =============================================================================
# Usage:
#   ./aura-install.sh --config $OUTPUT_FILE
# =============================================================================
EOF

    log_success "Configuration saved to: $OUTPUT_FILE"
}

# =============================================================================
# Main Entry Point
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                echo "Usage: $0 [--output FILE]"
                echo ""
                echo "Options:"
                echo "  --output FILE    Save configuration to FILE (default: aura-config.yaml)"
                echo "  -h, --help       Show this help message"
                exit 0
                ;;
            -o|--output)
                OUTPUT_FILE="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                exit 2
                ;;
        esac
    done
}

main() {
    parse_args "$@"
    print_banner

    echo "  Welcome to the Aura Configuration Wizard!"
    echo ""
    echo "  This wizard will guide you through configuring your Aura deployment."
    echo "  Press Ctrl+C at any time to cancel."
    echo ""
    echo "  Press Enter to begin..."
    read -r

    # Run wizard sections
    section_basic
    section_aws_region
    section_sizing
    section_network
    section_dns
    section_bedrock
    section_advanced

    # Show summary
    show_summary

    # Confirm and save
    prompt_yes_no "Save this configuration?" "y" "save_config"

    if [[ "$save_config" == true ]]; then
        save_configuration

        echo ""
        echo -e "${BOLD}Next Steps:${NC}"
        echo ""
        echo "  1. Review the configuration file:"
        echo "     cat $OUTPUT_FILE"
        echo ""
        echo "  2. Run the installer:"
        echo "     ./aura-install.sh --config $OUTPUT_FILE"
        echo ""
        echo "  3. For questions, visit: https://docs.aenealabs.com"
        echo ""
    else
        log_info "Configuration not saved. Run the wizard again when ready."
    fi
}

main "$@"
