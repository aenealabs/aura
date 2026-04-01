#!/bin/bash
##############################################################################
# Project Aura - CloudFormation Deployment Script
# Automates deployment of Bedrock infrastructure
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEMPLATE_FILE="$SCRIPT_DIR/aura-bedrock-infrastructure.yaml"

# Default values
STACK_NAME="aura-bedrock-infra"
ENVIRONMENT="development"
REGION="us-east-1"
ALERT_EMAIL=""
DAILY_BUDGET="10"
MONTHLY_BUDGET="100"

##############################################################################
# Helper Functions
##############################################################################

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Project Aura Bedrock infrastructure using CloudFormation.

OPTIONS:
    -e, --environment ENV    Environment (development|staging|production)
                            Default: development
    -r, --region REGION     AWS region
                            Default: us-east-1
    -s, --stack-name NAME   CloudFormation stack name
                            Default: aura-bedrock-infra
    -m, --email EMAIL       Email for budget alerts (REQUIRED)
    -d, --daily-budget N    Daily budget in USD
                            Default: 10
    -M, --monthly-budget N  Monthly budget in USD
                            Default: 100
    -v, --validate          Validate template only (don't deploy)
    -D, --delete            Delete the stack
    -h, --help              Show this help message

EXAMPLES:
    # Deploy development stack
    $0 --email you@example.com

    # Deploy production stack with custom budgets
    $0 -e production -m you@example.com -d 100 -M 2000

    # Validate template
    $0 --validate

    # Delete stack
    $0 --delete

EOF
    exit 1
}

##############################################################################
# Parse Command Line Arguments
##############################################################################

VALIDATE_ONLY=false
DELETE_STACK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -m|--email)
            ALERT_EMAIL="$2"
            shift 2
            ;;
        -d|--daily-budget)
            DAILY_BUDGET="$2"
            shift 2
            ;;
        -M|--monthly-budget)
            MONTHLY_BUDGET="$2"
            shift 2
            ;;
        -v|--validate)
            VALIDATE_ONLY=true
            shift
            ;;
        -D|--delete)
            DELETE_STACK=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

##############################################################################
# Validate Prerequisites
##############################################################################

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Install with: brew install awscli"
        exit 1
    fi
    print_success "AWS CLI found: $(aws --version)"

    # Check AWS credentials
    if ! aws sts get-caller-identity --region $REGION &> /dev/null; then
        print_error "AWS credentials not configured. Run: aws configure"
        exit 1
    fi

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_success "AWS credentials configured (Account: $ACCOUNT_ID)"

    # Check template exists
    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_error "Template file not found: $TEMPLATE_FILE"
        exit 1
    fi
    print_success "Template file found"

    # Validate environment
    if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
        print_error "Invalid environment: $ENVIRONMENT (must be development, staging, or production)"
        exit 1
    fi
    print_success "Environment validated: $ENVIRONMENT"
}

##############################################################################
# Validate Template
##############################################################################

validate_template() {
    print_header "Validating CloudFormation Template"

    if aws cloudformation validate-template \
        --template-body file://$TEMPLATE_FILE \
        --region $REGION &> /dev/null; then
        print_success "Template validation passed"
        return 0
    else
        print_error "Template validation failed"
        aws cloudformation validate-template \
            --template-body file://$TEMPLATE_FILE \
            --region $REGION
        return 1
    fi
}

##############################################################################
# Delete Stack
##############################################################################

delete_stack() {
    print_header "Deleting CloudFormation Stack"

    # Check if stack exists
    if ! aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION &> /dev/null; then
        print_warning "Stack $STACK_NAME does not exist"
        return 0
    fi

    print_warning "This will delete the following resources:"
    echo "  • IAM Role and Policies"
    echo "  • DynamoDB Table (with all cost data)"
    echo "  • Secrets Manager secrets"
    echo "  • SNS Topic and subscriptions"
    echo "  • CloudWatch Alarms"
    echo "  • CloudWatch Log Groups"
    echo ""
    read -p "Are you sure you want to delete stack '$STACK_NAME'? (yes/no): " -r
    echo

    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "Deletion cancelled"
        return 0
    fi

    print_info "Deleting stack: $STACK_NAME"

    aws cloudformation delete-stack \
        --stack-name $STACK_NAME \
        --region $REGION

    print_info "Waiting for stack deletion to complete..."

    if aws cloudformation wait stack-delete-complete \
        --stack-name $STACK_NAME \
        --region $REGION; then
        print_success "Stack deleted successfully"
        return 0
    else
        print_error "Stack deletion failed or timed out"
        return 1
    fi
}

##############################################################################
# Deploy Stack
##############################################################################

deploy_stack() {
    print_header "Deploying CloudFormation Stack"

    # Check email
    if [ -z "$ALERT_EMAIL" ]; then
        print_error "Email address required. Use --email option."
        exit 1
    fi

    print_info "Stack Name: $STACK_NAME"
    print_info "Environment: $ENVIRONMENT"
    print_info "Region: $REGION"
    print_info "Alert Email: $ALERT_EMAIL"
    print_info "Daily Budget: \$$DAILY_BUDGET"
    print_info "Monthly Budget: \$$MONTHLY_BUDGET"
    echo ""

    # Check if stack exists
    STACK_EXISTS=false
    if aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION &> /dev/null; then
        STACK_EXISTS=true
        print_info "Stack exists. Will update."
    else
        print_info "Stack does not exist. Will create."
    fi

    # Deploy
    if $STACK_EXISTS; then
        CHANGE_SET_NAME="aura-update-$(date +%s)"

        print_info "Creating change set: $CHANGE_SET_NAME"

        aws cloudformation create-change-set \
            --stack-name $STACK_NAME \
            --change-set-name $CHANGE_SET_NAME \
            --template-body file://$TEMPLATE_FILE \
            --parameters \
                ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
                ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
                ParameterKey=DailyBudgetUSD,ParameterValue=$DAILY_BUDGET \
                ParameterKey=MonthlyBudgetUSD,ParameterValue=$MONTHLY_BUDGET \
            --capabilities CAPABILITY_NAMED_IAM \
            --region $REGION

        print_info "Waiting for change set creation..."
        aws cloudformation wait change-set-create-complete \
            --stack-name $STACK_NAME \
            --change-set-name $CHANGE_SET_NAME \
            --region $REGION

        # Describe changes
        print_info "Changes to be applied:"
        aws cloudformation describe-change-set \
            --stack-name $STACK_NAME \
            --change-set-name $CHANGE_SET_NAME \
            --region $REGION \
            --query 'Changes[*].[ResourceChange.Action,ResourceChange.LogicalResourceId,ResourceChange.ResourceType]' \
            --output table

        # Confirm
        read -p "Apply these changes? (yes/no): " -r
        echo
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            print_info "Update cancelled"
            aws cloudformation delete-change-set \
                --stack-name $STACK_NAME \
                --change-set-name $CHANGE_SET_NAME \
                --region $REGION
            return 0
        fi

        print_info "Executing change set..."
        aws cloudformation execute-change-set \
            --stack-name $STACK_NAME \
            --change-set-name $CHANGE_SET_NAME \
            --region $REGION

        print_info "Waiting for stack update..."
        if aws cloudformation wait stack-update-complete \
            --stack-name $STACK_NAME \
            --region $REGION; then
            print_success "Stack updated successfully"
        else
            print_error "Stack update failed"
            return 1
        fi
    else
        print_info "Creating stack..."

        aws cloudformation create-stack \
            --stack-name $STACK_NAME \
            --template-body file://$TEMPLATE_FILE \
            --parameters \
                ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
                ParameterKey=AlertEmail,ParameterValue=$ALERT_EMAIL \
                ParameterKey=DailyBudgetUSD,ParameterValue=$DAILY_BUDGET \
                ParameterKey=MonthlyBudgetUSD,ParameterValue=$MONTHLY_BUDGET \
            --capabilities CAPABILITY_NAMED_IAM \
            --region $REGION \
            --tags \
                Key=Project,Value=Aura \
                Key=Environment,Value=$ENVIRONMENT \
                Key=ManagedBy,Value=CloudFormation

        print_info "Waiting for stack creation (this may take 3-5 minutes)..."
        if aws cloudformation wait stack-create-complete \
            --stack-name $STACK_NAME \
            --region $REGION; then
            print_success "Stack created successfully"
        else
            print_error "Stack creation failed"
            return 1
        fi
    fi

    # Display outputs
    print_header "Stack Outputs"
    aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table
}

##############################################################################
# Main Script
##############################################################################

main() {
    print_header "Project Aura - CloudFormation Deployment"

    check_prerequisites

    validate_template || exit 1

    if $VALIDATE_ONLY; then
        print_success "Template validation complete. No deployment performed."
        exit 0
    fi

    if $DELETE_STACK; then
        delete_stack
        exit $?
    fi

    deploy_stack || exit 1

    print_header "Deployment Complete!"

    print_success "Infrastructure is ready"
    echo ""
    print_info "Next steps:"
    echo "  1. Confirm SNS email subscription (check your email)"
    echo "  2. Enable Bedrock model access:"
    echo "     https://console.aws.amazon.com/bedrock/"
    echo "  3. Validate setup:"
    echo "     python3 deploy/validate_aws_setup.py"
    echo "  4. Test Bedrock service:"
    echo "     python3 src/services/bedrock_llm_service.py"
    echo ""
    print_info "View stack in AWS Console:"
    echo "  https://console.aws.amazon.com/cloudformation/home?region=$REGION#/stacks"
}

main
