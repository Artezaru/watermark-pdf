SHELL := /bin/bash

# variables
venv ?= venv

message ?=
push ?=
branch ?=

level ?=

# Current package version, read live from .bumpver.toml (the single
# source of truth `make bump` itself updates), so tagging always uses
# the version actually in effect for the package -- never hardcoded.
version := $(shell grep -m1 '^current_version' .bumpver.toml | sed -E 's/current_version = "([^"]+)"/\1/')

# Default help command to list available Sphinx options
help:
	@echo "Available commands:"
	@echo "  help       - Show this help message"
	@echo "  main       - Activate the venv and run \"python3 -m watermark_pdf\""
	@echo "  bump       - [level={major/minor/patch}] Update the version of the package"
	@echo "  git        - git add commit push version and commit"

.PHONY: help main bump git

# Run the application (inside the venv)
main:
	@\
	echo "Activating venv: $(venv)" && \
	source $(venv)/bin/activate && \
	python3 -m watermark_pdf

# Update the version of the package
bump:
	@\
	echo "Checking for version update level..." && \
	if [ -z "$(level)" ]; then \
		echo "Error: level variable is not set. Use 'make bump level=patch' (or major/minor)"; \
		exit 1; \
	fi && \
	echo "Updating version with level: $(level)" && \
	bumpver update --$(level) --no-fetch && \
	echo "Version updated successfully."

# Git Push origin Branch
git:
	@\
	echo "Checking for required variables: message, branch, push..." && \
	if [ -z "$(message)" ]; then \
		echo "Error: message variable is not set. Use 'make git message=\"Your commit message\"'"; \
		exit 1; \
	fi && \
	if [ -z "$(branch)" ]; then \
		echo "Error: branch variable is not set. Use 'make git branch=\"branch_name\"'"; \
		exit 1; \
	fi && \
	if [ -z "$(push)" ]; then \
		echo "Error: push variable is not set. Use 'make git push=true' to enable pushing or 'make git push=false' to disable pushing"; \
		exit 1; \
	fi && \
	if [ -z "$(version)" ]; then \
		echo "Error: could not determine the current package version from .bumpver.toml"; \
		exit 1; \
	fi && \
	echo "Committing changes with message: $(message) on branch: $(branch)" && \
	git checkout $(branch) && \
	git add -A . && \
	git commit -m "$(message)" && \
	if [ "$(push)" = "true" ]; then \
		echo "Pushing changes to origin $(branch)..."; \
		git push origin $(branch); \
		echo "Retagging v$(version) on origin..."; \
		git tag -d v$(version) 2>/dev/null || true; \
		git push origin :refs/tags/v$(version) 2>/dev/null || true; \
		git tag v$(version); \
		git push origin v$(version); \
	else \
		echo "Push is disabled. Skipping git push and tag update."; \
	fi && \
	echo "Git operations completed successfully."