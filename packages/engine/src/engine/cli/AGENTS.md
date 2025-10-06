# AGENT BRIEF - CLI

Purpose: Hold the command-line entry points that drive engine workflows, scenario runs, and operational tooling.

Guidance for future agents:
- Surface only thin wrappers around orchestrators; heavier logic belongs in core or layer modules.
- Document new flags and defaults inside the command implementation.
- Keep commands deterministic and defer IO validation to the state packages.

