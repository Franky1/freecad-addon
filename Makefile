.PHONY: all update venv venvupdate cleanpy cleanvenv cleanall help

# run one shell only
.ONESHELL: all update venv venvupdate cleanpy cleanvenv cleanall help

# disable running of targets in parallel
.NOTPARALLEL: all update venv venvupdate cleanpy cleanvenv cleanall help

# predefined variables
CURRDIRECTORY := $(notdir $(CURDIR))
DOCKERTAG := $(shell python -c "print('$(CURRDIRECTORY)'.lower())"):latest

# Detect shell capabilities.
SHELL_BASENAME := $(notdir $(SHELL))
# Strip extension to normalize (e.g. powershell.exe -> powershell, bash.exe -> bash)
SHELL_CORE := $(basename $(SHELL_BASENAME))
KNOWN_POSIX_SHELLS := sh bash zsh ksh ash dash busybox
# Only mark POSIX if the core name matches the whitelist (prevents false positive on 'powershell')
HAVE_POSIX_SHELL := $(filter $(KNOWN_POSIX_SHELLS),$(SHELL_CORE))

ifeq ($(OS),Windows_NT)
	# Windows defaults (cmd / PowerShell)
	PYTHONVENV := .venv/Scripts/
	PYTHONVENVEXE := .venv/Scripts/python.exe
	RM_CMD := del /Q /S
	WHERE_CMD := where
	ECHO_BLANK := echo.
	ifeq ($(SHELL),sh.exe)
		# Explicitly keep Windows settings when PowerShell detected
		ECHO_BLANK := echo .
	else ifneq ($(HAVE_POSIX_SHELL),)
		# If NOT PowerShell but actually a POSIX-like shell, override with POSIX tooling
		RM_CMD := rm -rf
		WHERE_CMD := which
		ECHO_BLANK := echo
	endif
else
	PYTHONVENV := .venv/bin/
	PYTHONVENVEXE := .venv/bin/python
	RM_CMD := rm -rf
	WHERE_CMD := which
	ECHO_BLANK := echo
endif

# default target
all: cleanpy update venv
	@$(ECHO_BLANK)
	@echo "******************* all FINISHED *******************"
	@$(ECHO_BLANK)

# local update of pip/virtualenv
update:
	@echo "******************* update START *******************"
	@$(ECHO_BLANK)
	python -m pip install --upgrade pip setuptools wheel poetry virtualenv uv ruff pylint mypy pyright
	@$(ECHO_BLANK)
	@echo "******************* update FINISHED *******************"
	@$(ECHO_BLANK)

# target for building the python venv
venv:
	@echo "******************* venv START *******************"
	@$(ECHO_BLANK)
	@echo "Local Python Version..."
	python --version
	$(WHERE_CMD) python
	@$(ECHO_BLANK)
	@echo "Make Virtual Environment..."
	uv venv --python 3.11 --seed --clear
	@$(ECHO_BLANK)
	@echo "Check Virtual Environment Python Version..."
	$(PYTHONVENVEXE) --version
	$(PYTHONVENVEXE) -c "import sys; print(sys.executable)"
	@$(ECHO_BLANK)
	@echo "Upgrade project dependencies..."
	uv lock --upgrade
	@$(ECHO_BLANK)
	@echo "Install project dependencies..."
	@$(ECHO_BLANK)
	uv sync --no-install-project
	@$(ECHO_BLANK)
	@echo "Check for conflicts..."
	uv pip check
	@$(ECHO_BLANK)
	@echo "Check for outdated dependencies and just list them..."
	$(PYTHONVENVEXE) -m pip list --outdated
	@$(ECHO_BLANK)
	@echo "******************* virtualenv venv FINISHED *******************"
	@$(ECHO_BLANK)

# target for upgrading venv (assumes venv exists)
venvupdate:
	@echo "******************* venvupdate START *******************"
	@$(ECHO_BLANK)
	@echo "Check Virtual Environment Python Version..."
	$(PYTHONVENVEXE) --version
	$(PYTHONVENVEXE) -c "import sys; print(sys.executable)"
	@$(ECHO_BLANK)
	@echo "Upgrade project dependencies..."
	uv lock --upgrade
	@$(ECHO_BLANK)
	@echo "Install project dependencies..."
	@$(ECHO_BLANK)
	uv sync --no-install-project
	@$(ECHO_BLANK)
	@echo "Check for conflicts..."
	uv pip check
	@$(ECHO_BLANK)
	@echo "Check for outdated dependencies and just list them..."
	$(PYTHONVENVEXE) -m pip list --outdated
	@$(ECHO_BLANK)
	@echo "******************* venvupdate FINISHED *******************"
	@$(ECHO_BLANK)

# remove cache files
cleanpy:
	@echo "******************* cleanpy START *******************"
	@$(ECHO_BLANK)
	$(RM_CMD) __pycache__
	@$(ECHO_BLANK)
	@echo "******************* cleanpy FINISHED *******************"
	@$(ECHO_BLANK)

# remove venv
cleanvenv:
	@echo "******************* cleanvenv START *******************"
	@$(ECHO_BLANK)
	$(RM_CMD) .venv
	$(RM_CMD) uv.lock
	@$(ECHO_BLANK)
	@echo "******************* cleanvenv FINISHED *******************"
	@$(ECHO_BLANK)

# clean all
cleanall: cleanpy cleanvenv
	@$(ECHO_BLANK)
	@echo "******************* cleanall FINISHED *******************"
	@$(ECHO_BLANK)

# help target
help:
	@echo "Available targets:"
	@echo "  all        - Clean Python cache, update tools, and create/setup venv"
	@echo "  update     - Upgrade pip, setuptools, wheel, poetry, virtualenv, uv, and ruff"
	@echo "  venv       - Create and set up Python virtual environment with dependencies"
	@echo "  venvupdate - Update dependencies in existing venv (requires venv to exist)"
	@echo "  cleanpy    - Remove Python cache files (__pycache__)"
	@echo "  cleanvenv  - Remove the virtual environment (.venv)"
	@echo "  cleanall   - Remove cache and venv"
	@echo "  help       - Show this help message"
