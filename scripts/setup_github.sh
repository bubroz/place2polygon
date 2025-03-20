#!/bin/bash

# Script to set up and connect a local repository to GitHub

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs -0)
else
    echo "Error: .env file not found"
    exit 1
fi

# Check if GitHub token is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN not found in .env file"
    exit 1
fi

# Set default values
REPO_NAME=${1:-"place2polygon"}
REPO_DESC=${2:-"A tool for extracting location mentions from text and finding their precise polygon boundaries"}
VISIBILITY=${3:-"public"}

echo "Setting up GitHub repository: $REPO_NAME"
echo "Description: $REPO_DESC"
echo "Visibility: $VISIBILITY"

# Create the repository on GitHub using the GitHub API
echo "Creating repository on GitHub..."
curl -s -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/user/repos \
    -d "{\"name\":\"$REPO_NAME\",\"description\":\"$REPO_DESC\",\"private\":$([ "$VISIBILITY" = "private" ] && echo "true" || echo "false")}" > /dev/null

# Get the GitHub username
GITHUB_USERNAME=$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | grep -o '"login": "[^"]*' | sed 's/"login": "//')

if [ -z "$GITHUB_USERNAME" ]; then
    echo "Error: Could not get GitHub username"
    exit 1
fi

echo "GitHub username: $GITHUB_USERNAME"

# Set the remote origin
echo "Setting up remote origin..."
git remote add origin "https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com/$GITHUB_USERNAME/$REPO_NAME.git"

# Push to GitHub
echo "Pushing to GitHub..."
git push -u origin main

echo "Repository setup complete!"
echo "Your repository is available at: https://github.com/$GITHUB_USERNAME/$REPO_NAME" 