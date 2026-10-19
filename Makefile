# AILineage spec -- validation targets.
# Requirements: python3 (3.10+), openssl (3.0+), check-jsonschema (pip),
# markdownlint-cli2 (npm). See CONTRIBUTING.md.

SHELL          := /bin/bash
PYTHON         ?= python3
CHECK_JSONSCHEMA ?= check-jsonschema
MARKDOWNLINT   ?= markdownlint-cli2

SCHEMA         := schema/lineage-0.1.json
BASE_URI       := file://$(CURDIR)/$(SCHEMA)
CJ             := $(CHECK_JSONSCHEMA) --schemafile $(SCHEMA) --base-uri "$(BASE_URI)"
VALID          := $(sort $(wildcard fixtures/valid/*.json))
INVALID        := $(sort $(wildcard fixtures/invalid/*.json))
# Fixtures that are schema-valid but violate verifier-only rules (SPEC.md 9).
SEMANTIC_INVALID := fixtures/invalid/parent-self-reference.json
SCHEMA_INVALID := $(filter-out $(SEMANTIC_INVALID),$(INVALID))
JSON_FILES     := $(shell find . -name '*.json' -not -path './node_modules/*' -not -path './.git/*')

.PHONY: all validate validate-schema validate-valid validate-invalid validate-semantic \
        validate-fixtures lint lint-md lint-json fixtures-regen test-vectors help

all: validate lint test-vectors

help:
	@echo "make validate        schema x fixtures (valid MUST pass, invalid MUST fail) + fixture crypto checks"
	@echo "make lint            markdownlint + JSON syntax"
	@echo "make test-vectors    recompute CANONICALIZATION.md test vectors"
	@echo "make fixtures-regen  regenerate data, fixtures, examples and generated doc blocks"

validate: validate-schema validate-valid validate-invalid validate-semantic validate-fixtures

validate-schema:
	@$(CHECK_JSONSCHEMA) --check-metaschema $(SCHEMA) schema/defs/*.json

validate-valid:
	@$(CJ) $(VALID)

validate-invalid:
	@fail=0; for f in $(SCHEMA_INVALID); do \
	  out=$$($(CJ) "$$f" 2>&1); rc=$$?; \
	  if [ $$rc -eq 0 ]; then echo "UNEXPECTED PASS: $$f"; fail=1; \
	  elif ! grep -q "Schema validation errors" <<<"$$out"; then echo "TOOL ERROR (not a validation failure): $$f"; echo "$$out"; fail=1; \
	  else echo "ok (rejected) $$f"; fi; \
	done; exit $$fail

validate-semantic:
	@fail=0; for f in $(SEMANTIC_INVALID); do \
	  if ! $(CJ) "$$f" >/dev/null 2>&1; then echo "EXPECTED SCHEMA PASS: $$f"; fail=1; fi; \
	  if $(PYTHON) fixtures/regen.py semantic "$$f" >/dev/null; then echo "UNEXPECTED SEMANTIC PASS: $$f"; fail=1; \
	  else echo "ok (semantic reject) $$f"; fi; \
	done; exit $$fail

validate-fixtures:
	@$(PYTHON) fixtures/regen.py check

lint: lint-md lint-json

lint-md:
	@$(MARKDOWNLINT) "**/*.md" "#node_modules" "#fixtures/data"

lint-json:
	@fail=0; for f in $(JSON_FILES); do \
	  $(PYTHON) -m json.tool "$$f" >/dev/null || { echo "invalid JSON: $$f"; fail=1; }; \
	done; [ $$fail -eq 0 ] && echo "lint-json: $(words $(JSON_FILES)) files ok"; exit $$fail

fixtures-regen:
	@$(PYTHON) fixtures/regen.py regen

test-vectors:
	@$(PYTHON) fixtures/regen.py test-vectors
