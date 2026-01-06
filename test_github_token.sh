#!/bin/bash
set -e
echo "Testing GitHub token with ls-remote..."
GIT_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/dn-scribe/nebenchat-data.git"
echo "Using URL: $GIT_URL"
git ls-remote "$GIT_URL"
echo "If you see refs above, the token is valid for read access."
echo "Now testing push access (this will not actually push, just check auth)..."
git clone --depth=1 "$GIT_URL" test_token_repo
cd test_token_repo
git config user.name "Test User"
git config user.email "test@example.com"
touch test_token_file.txt
git add test_token_file.txt
git commit -m "test commit"
echo "Attempting dry-run push..."
git push --dry-run origin HEAD:main
cd ..
rm -rf test_token_repo
echo "If you see 'Everything up-to-date' or 'refs/heads/main', push auth is OK."
