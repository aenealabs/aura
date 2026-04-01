#!/bin/bash

# =================================================================
# GITHUB REPOSITORY SETUP SCRIPT
# Purpose: Initializes the local repository, stages all generated
# files, creates a secure .gitignore, and performs the initial push.
# This aligns with SOX/CMMC compliance by ignoring sensitive files.
# =================================================================

# 1. Configuration (Your actual repository URL)
REPO_URL="https://github.com/aenealabs/aura.git"
MAIN_BRANCH="main"
DEV_BRANCH="develop"

echo "Starting repository setup for: ${REPO_URL}"

# 2. Check if Git is initialized
if [ ! -d ".git" ]; then
    echo "Initializing new Git repository..."
    git init
fi

# 3. Create a secure .gitignore file
echo "Creating/Updating .gitignore for security compliance..."
cat << EOF > .gitignore
# Ignore system-level files
.DS_Store
*.pyc
__pycache__/

# Critical Security: Ignore environment variables and secrets
.env
*.key
*.pem
*.secret

# IDE and Editor files
.vscode/
.idea/

# Large binaries/Outputs
/output/
/data/
EOF

# 4. Stage all current files
echo "Staging all project files..."
git add .
# Remove the empty/ignored files from staging
git rm --cached setup_repo.sh 2>/dev/null

# 5. Initial Commit
COMMIT_MESSAGE="Initial CKGE Architecture Commit: Core Agents, Tests, and Security Hardening"
echo "Creating initial commit..."
git commit -m "$COMMIT_MESSAGE"

# 6. Set up remote, branches, and push
echo "Setting remote origin to: ${REPO_URL}"
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"

echo "Setting up branches and pushing to GitHub..."
# Create and push the main branch
git branch -M "$MAIN_BRANCH"
git push -u origin "$MAIN_BRANCH"

# Create and push the develop branch
git checkout -b "$DEV_BRANCH"
git push -u origin "$DEV_BRANCH"

git checkout "$MAIN_BRANCH"

echo "================================================================="
echo "✅ Repository setup complete!"
echo "Project files are now pushed to ${REPO_URL} on both main and develop."
echo "NEXT STEP: Execute the React Front-End build."
echo "================================================================="
