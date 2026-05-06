# OpenEnv quick reference (for the umbrella skill)

The umbrella skill should read this when planning the OpenEnv variant. For the full implementation flow, defer to the `generate-openenv-env` skill.

## What OpenEnv is

HTTP server exposing tools via the **MCP** (Model Context Protocol) shape. The runtime is FastAPI; tools are FastMCP-decorated functions. The client (`MCPToolClient`) discovers tools via `list_tools()` and calls them via `call_tool(name, **args)`.

## Core types

| Symbol | Source | What it is |
|---|---|---|
| `MCPEnvironment` | `openenv.core.env_server.mcp_environment` | Subclass this for the env. Holds a `FastMCP` instance and dispatches tool calls. |
| `create_app` | `openenv.core.env_server.http_server` | Builds the FastAPI app; takes the env class + action/observation types. |
| `CallToolAction`, `CallToolObservation` | `openenv.core.env_server.mcp_types` | The wire types for tool dispatch. |
| `Action`, `Observation`, `State` | `openenv.core.env_server.types` | Base classes for typed envs. |
| `MCPToolClient` | `openenv.core.mcp_client` | Sync/async client. Use `.sync()` as a context manager. |
| `Image` (FastMCP) | `fastmcp.utilities.types` | Helper for image tool returns: `Image(data=bytes, format="png")`. |

## Reward model

**External**. The env doesn't return a reward per tool call; the trainer or rollout computes it from the trajectory. Pair with TRL's `GRPOTrainer` reward function, or compute inline in the rollout.

## When OpenEnv beats ORS / Verifiers

- You want MCP ecosystem compatibility (Claude Desktop, MCP Inspector, etc.)
- You need a full Gradio UI bundled with the env
- You're targeting Meta's OpenEnv ecosystem / HF Spaces deployment
- The reward depends on the whole trajectory (not per-call)

## When OpenEnv loses

- You want **per-call** reward — pick ORS instead.
- You don't need HTTP at all — pick Verifiers.
- The tool schemas need fancy validation that FastMCP's pydantic introspection can't handle (rare).
