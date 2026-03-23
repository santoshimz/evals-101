# `mcp-201` Baseline Contract

This document freezes the current `mcp-201` behavior that `evals-101` treats as the product baseline.

## Tools

- `crop_images`
- `colorize_images`
- `run_prompt_workflow`

## Workflow labels

- `crop_images`
- `colorize_images`
- `crop_then_colorize`
- `clarify`

`run_prompt_workflow` is the main live integration point for prompt-driven evals. It uses AI planning first and falls back to heuristics when no planner key is available.

## Request expectations

- image payloads are base64 encoded and validated as real images
- file names must end with `.jpg`, `.jpeg`, `.png`, or `.webp`
- at least one image is required
- the current maximum is 5 images per request
- the current file-size limit is 6 MB per image
- `credential_mode=server` uses the server Gemini key when configured
- `credential_mode=byok` requires a request-level Gemini key

## Security baseline

- `Authorization` headers must be enforced when `MCP_201_REQUIRE_AUTH=true`
- `credential_mode=server` must not accept a request-level Gemini key
- `credential_mode=byok` requires a request-level Gemini key
- BYOK credentials must never be logged or persisted in eval artifacts
- secret-bearing errors must be redacted before being stored in reports

## Seed deterministic corpus

The deterministic gate corpus covers:

- crop-only prompt
- colorize-only prompt
- crop-then-colorize prompt
- ambiguous prompt that should clarify rather than guess
