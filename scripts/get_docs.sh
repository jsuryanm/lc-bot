#!/usr/bin/env bash
# Download (or update) the LangChain docs source into data/langchain-docs.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d data/langchain-docs/.git ]; then
  git -C data/langchain-docs pull --ff-only
else
  git clone --depth 1 https://github.com/langchain-ai/docs data/langchain-docs
fi
git -C data/langchain-docs log -1 --format='Docs commit: %h (%cd)'