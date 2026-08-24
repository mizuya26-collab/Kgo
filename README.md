# Kgo

Autonomous Self-Healing / Self-Evolution Engine

## Purpose

This repository contains the persistent source code and evolution
state for the autonomous software agent.

## Architecture

- Diagnosis
- Root Cause Analysis
- Self Healing
- Rollback
- Tool Expansion
- Tool Validation
- Knowledge Memory
- Self Evolution
- Health Monitoring
- Watchdog
- Safety Policy
- Regression Testing

## Runtime

Primary runtime:

- Google Colab
- NVIDIA Tesla T4
- Ollama
- gpt-oss:20b

Fallback runtime:

- Local CPU

## Recovery

Colab `/content` is considered volatile.

Persistent project data must be synchronized with GitHub.

## Safety

The agent must never:

- mutate code without validation
- persist failed mutations
- install unverified tools
- bypass rollback
- expose credentials
- endlessly retry failed repairs
