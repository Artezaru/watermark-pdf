# =============================================================================
#  Makefile - Python project template
#
#  Only edit the "Project settings" block below for a new repository.
#
#  Typical release:
#    make bump level=patch
#    make commit message="Release 1.2.3"
#    make push
#    make pushtag          -> launches build.yml, publish.yml, docs.yml
#
#  Documentation (call in this order):
#    make clean
#    make html
#    make open
# =============================================================================

# --- Project settings --------------------------------------------------------
# Python package folder (used by "make main" and to find __version__).
PACKAGE_DIR       := watermark_pdf
# File containing __version__ = "x.y.z" (same as VERSION_FILE in publish.yml).
VERSION_FILE      := $(PACKAGE_DIR)/__version__.py
TESTS_DIR         := tests
DOCS_REQUIREMENTS := sphinx pydata-sphinx-theme sphinx-copybutton sphinx-gallery sphinx-design
DEV_REQUIREMENTS  := pytest bumpver build

# --- Sphinx ------------------------------------------------------------------
SPHINXOPTS ?=
SOURCEDIR  := docs/source
BUILDDIR   := docs/build

# --- Command-line variables --------------------------------------------------
venv    ?= venv
level   ?=
message ?=
branch  ?=
force   ?= false

# =============================================================================
#  Nothing to change below this line.
# =============================================================================

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PYTHON  := $(venv)/bin/python

BUMPVER_FILE = .bumpver.toml
version = $(shell sed -n 's/^current_version *= *"\(.*\)"/\1/p' $(BUMPVER_FILE))

.PHONY: help install version main test bump clean html open commit push pushtag

# -----------------------------------------------------------------------------
#  Help
# -----------------------------------------------------------------------------
help:
	@echo "Usage: make <target> [variable=value]"
	echo ""
	echo "Setup"
	echo "  install   [venv=venv]  Create the venv if needed, pip install -e . + docs/dev tools"
	echo ""
	echo "Development"
	echo "  version                Show the current version of the package"
	echo "  main      [venv=venv]  Run the application (python -m $(PACKAGE_DIR))"
	echo "  test      [venv=venv]  Run the tests with pytest ($(TESTS_DIR)/)"
	echo "  bump      level=major|minor|patch  Update the package version with bumpver"
	echo ""
	echo "Documentation (in this order)"
	echo "  clean                  Remove $(BUILDDIR)/ and generated Sphinx files"
	echo "  html      [venv=venv]  Build the HTML docs in $(BUILDDIR)/html/"
	echo "  open                   Open $(BUILDDIR)/html/index.html in the browser"
	echo ""
	echo "Git"
	echo "  commit    message=\"...\"  git add -A + git commit"
	echo "  push      [branch=...]   git push origin <branch> (default: current branch)"
	echo "  pushtag   [force=true]   Tag HEAD as v<__version__> and push the tag"
	echo "                           (launches the GitHub Actions workflows)"
	echo ""
	echo "Current version: $(version)"

# -----------------------------------------------------------------------------
#  Setup
# -----------------------------------------------------------------------------
install:
	@if [ ! -d "$(venv)" ]; then
		echo "Creating virtual environment at $(venv)..."
		python3 -m venv "$(venv)"
	fi
	echo "Installing the package in editable mode..."
	"$(PYTHON)" -m pip install --upgrade pip
	"$(PYTHON)" -m pip install -e .
	echo "Installing documentation and development tools..."
	"$(PYTHON)" -m pip install $(DOCS_REQUIREMENTS) $(DEV_REQUIREMENTS)
	echo "Installation complete."

# -----------------------------------------------------------------------------
#  Development
# -----------------------------------------------------------------------------
version:
	@echo "$(version)"

main:
	@"$(PYTHON)" -m $(PACKAGE_DIR)

test:
	@"$(PYTHON)" -m pytest $(TESTS_DIR)

bump:
	@\
	case "$(level)" in \
		major|minor|patch) ;; \
		*) echo "Error: use 'make bump level=major|minor|patch'"; exit 1 ;; \
	esac && \
	echo "Current version: $(version)" && \
	bumpver update --$(level) --no-fetch && \
	echo "New version: $$(sed -n 's/^current_version *= *"\(.*\)"/\1/p' $(BUMPVER_FILE))"

# -----------------------------------------------------------------------------
#  Documentation
# -----------------------------------------------------------------------------
clean:
	@echo "Removing $(BUILDDIR)/ and generated Sphinx files..."
	rm -rf "$(BUILDDIR)"
	rm -rf "$(SOURCEDIR)/_autosummary" \
	       "$(SOURCEDIR)/_gallery" \
	       "$(SOURCEDIR)/_gallery_backreferences" \
	       "$(SOURCEDIR)/sg_execution_times.rst"
	echo "Clean complete."

html:
	@echo "Building HTML documentation in $(BUILDDIR)/html/..."
	"$(venv)/bin/sphinx-build" -b html $(SPHINXOPTS) "$(SOURCEDIR)" "$(BUILDDIR)/html"
	echo "Documentation built: $(BUILDDIR)/html/index.html"

open:
	@INDEX="$(BUILDDIR)/html/index.html"
	if [ ! -f "$$INDEX" ]; then
		echo "Error: $$INDEX not found. Run 'make html' first."
		exit 1
	fi
	if command -v xdg-open >/dev/null 2>&1; then
		xdg-open "$$INDEX" >/dev/null 2>&1
	else
		open "$$INDEX"
	fi

# -----------------------------------------------------------------------------
#  Git
# -----------------------------------------------------------------------------
commit:
	@if [ -z "$(message)" ]; then
		echo 'Error: use make commit message="Your commit message"'
		exit 1
	fi
	git add -A
	if git diff --cached --quiet; then
		echo "Nothing to commit."
		exit 0
	fi
	git commit -m "$(message)"

push:
	@BRANCH="$(branch)"
	if [ -z "$$BRANCH" ]; then
		BRANCH="$$(git rev-parse --abbrev-ref HEAD)"
	fi
	echo "Pushing $$BRANCH to origin..."
	git push origin "$$BRANCH"

pushtag:
	@VERSION="$(version)"
	if [ -z "$$VERSION" ]; then
		echo "Error: could not read __version__ from $(VERSION_FILE)"
		exit 1
	fi
	TAG="v$$VERSION"

	# The tag must point to a committed and pushed state.
	if [ -n "$$(git status --porcelain)" ]; then
		echo "Error: uncommitted changes. Run 'make commit' first."
		exit 1
	fi
	if git rev-parse '@{u}' >/dev/null 2>&1 && [ -n "$$(git rev-list '@{u}..HEAD')" ]; then
		echo "Error: local commits not pushed. Run 'make push' first."
		exit 1
	fi

	# An existing tag is only moved with force=true.
	if git rev-parse -q --verify "refs/tags/$$TAG" >/dev/null \
	   || git ls-remote --exit-code --tags origin "refs/tags/$$TAG" >/dev/null 2>&1; then
		if [ "$(force)" != "true" ]; then
			echo "Error: tag $$TAG already exists."
			echo "  - New release: 'make bump level=...' then commit/push/pushtag."
			echo "  - Move the tag anyway: 'make pushtag force=true'"
			echo "    (PyPI will refuse to upload the same version twice)."
			exit 1
		fi
		echo "Moving existing tag $$TAG..."
		git tag -d "$$TAG" >/dev/null 2>&1 || true
		git push origin ":refs/tags/$$TAG" || true
	fi

	git tag "$$TAG"
	git push origin "$$TAG"
	echo "Tag $$TAG pushed: GitHub Actions workflows started."