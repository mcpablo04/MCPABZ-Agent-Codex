# MCPABZ Agent Codex

A Windows desktop assistant for working with local projects. It connects to FreeLLMAPI, Ollama, GitHub Copilot, and OpenAI-compatible providers. The agent can inspect files, propose changes, run approved commands, and use an optional browser and voice input.

## Start

Install Python with Tkinter, then double-click `Start Coding Agent.bat`. Open a project folder and choose a provider and model in Settings. Provider availability, model features, usage limits, and charges depend on the provider.

FreeLLMAPI runs separately. Its local endpoint is selected by default; it needs a running FreeLLMAPI service and its unified API key. Ollama also runs separately and needs a compatible local model.

## Approvals and data

The default mode asks before file changes and commands. Smart approve allows a limited set of low-risk documentation additions and version checks; other changes and commands ask. Review the proposed action before approving it.

The agent stores saved conversations and change history under Windows Local AppData in `MCPABZ Agent Codex`. Conversation text and project content included in a request are sent to the selected model provider. Change history is not encrypted and is not a replacement for backups or version control.

## Optional components

- **Voice:** follow [VOICE_SETUP.md](VOICE_SETUP.md). The local voice model and its Python environment are downloaded separately.
- **Browser:** the embedded browser and agent-controlled browser require optional `tkwry` and Playwright dependencies and their browser runtime. These machine-specific dependencies are not bundled in this source snapshot.
- **GitHub Copilot:** requires the Copilot SDK and CLI, Node.js, and an authenticated GitHub Copilot account. These dependencies and credentials are not bundled.
- **MCP servers:** configure servers locally. `mcp_config.json` is intentionally excluded because configurations may contain private data.

This is an initial private source snapshot. Optional component setup and redistribution licenses still need review before a public release.
