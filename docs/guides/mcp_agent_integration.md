# Model Context Protocol (MCP) Agent Integration

This guide details how external AI agents, developer IDEs, and automated workflows interact with **Specsynth** and **Perandam Space Intelligence (PSI)** using the **Model Context Protocol (MCP)** (North Star Pillar 4).

---

## 🔌 Architecture Overview

Specsynth provides a dual-runtime MCP architecture with **100% schema and behavioral parity**:

```
+-------------------------------------------------------------+
|                     External MCP Clients                     |
|        (Claude Code, Cursor, Cline, Windsurf, Antigravity)  |
+-------------------------------------------------------------+
                              |
                     Standard JSON-RPC 2.0
                              |
               +--------------+--------------+
               |                             |
               v                             v
     [Python MCP Server]           [Node.js MCP Server]
 `specsynth.mcp.server`       `perandam-psi/mcp_server.mjs`
 (High-perf in-flight GEMM)    (Direct Three.js stage driver)
```

Both servers implement the exact same canonical tool registry defined in `specsynth.contracts.mcp`.

---

## 🛠️ Canonical MCP Tools Reference

| Tool Name | Parameters | Purpose |
| :--- | :--- | :--- |
| `specsynth_calculate_cosmology` | `redshift` (float, required), `h0`, `om0` | Returns exact closed-form cosmological distances ($d_L, d_A, d_C, \mu$) and lookback times. |
| `specsynth_list_filters` | `instrument` (string, optional) | Lists all available telescope and instrument filter sets (JWST, Roman, Euclid, Rubin, HST). |
| `specsynth_inspect_galaxy` | `galaxy_id` (string, required), `base` | Extracts full physical parameters, SFH mass fractions, synthetic photometry, and SED. |
| `specsynth_get_3d_galaxy` | `galaxy_id` (string, required), `coordinate_frame`, `max_particles` | Returns 3D particle distribution, kinematics, stellar ages, metallicities, and morphology. |
| `specsynth_get_evolution_track` | `galaxy_id` (string, required), `dataset` | Returns progenitor evolutionary track, merger tree, and mass assembly across redshift $z$. |
| `specsynth_run_sentry_audit` | `base` (string), `sample_size` (int) | Runs 4-tier scientific QA validation suite on catalog photometry and outputs audit certification. |
| `specsynth_remediate_catalog` | `base`, `output_csv`, `confirm_destructive` | Autonomous agent remediation isolating anomaly root causes and producing clean catalog. |
| `specsynth_query_hypotheses` | `min_sigma`, `limit`, `dataset` | Retrieves high-redshift discovery profiles and anomaly hypotheses from deep mock catalogs. |
| `specsynth_check_bridge_status` | `host` (string) | Verifies live connectivity between the frontend stage viewer and Python contraction backend. |
| `specsynth_get_system_info` | None | Returns host hardware info, CPU threads, RAM, and GPU/BLAS acceleration capabilities. |

---

## ⚙️ Configuring MCP Clients

### 1. Claude Desktop / Claude Code
Add the server definition to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "specsynth-python": {
      "command": "python",
      "args": ["-m", "specsynth.mcp.server"],
      "cwd": "/path/to/specsynth"
    },
    "specsynth-node": {
      "command": "node",
      "args": ["perandam-psi/mcp_server.mjs"],
      "cwd": "/path/to/specsynth"
    }
  }
}
```

### 2. Cursor IDE
Under **Cursor Settings > Features > MCP**, click **Add New MCP Server**:
- **Name**: `specsynth`
- **Type**: `command`
- **Command**: `python -m specsynth.mcp.server`

---

## 💻 Sample Programmatic Execution

You can test tools directly over standard I/O pipes using JSON-RPC 2.0:

### Calculate Precise Cosmological Distances
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"specsynth_calculate_cosmology","arguments":{"redshift":2.0}}}' | python -m specsynth.mcp.server
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"redshift\": 2.0,\n  \"h0\": 67.74,\n  \"om0\": 0.3089,\n  \"luminosity_distance_mpc\": 15937.13,\n  \"comoving_distance_mpc\": 5312.38,\n  \"angular_diameter_distance_mpc\": 1770.79,\n  \"distance_modulus\": 46.012,\n  \"lookback_time_gyr\": 10.515,\n  \"cosmic_age_gyr\": 3.288\n}"
      }
    ]
  }
}
```

### Calculate Precise Cosmological Distances
```bash
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"specsynth_calculate_cosmology","arguments":{"redshift":2.0}}}' | node perandam-psi/mcp_server.mjs
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"redshift\": 2,\n  \"h0\": 67.74,\n  \"om0\": 0.3089,\n  \"comoving_distance_mpc\": 5312.39,\n  \"luminosity_distance_mpc\": 15937.17,\n  \"angular_diameter_distance_mpc\": 1770.8,\n  \"distance_modulus\": 46.012,\n  \"lookback_time_gyr\": 10.515,\n  \"cosmic_age_gyr\": 3.288\n}"
      }
    ]
  }
}
```

---

## 🚀 Supported Transports & Lifecycle

Specsynth MCP servers use standard **JSON-RPC 2.0 over standard I/O (`stdio`)** as the primary, production-grade transport for local AI agents, IDEs, and workflow engines.

### stdio Message Framing
- Each message is a single UTF-8 encoded JSON object terminated by a newline (`\n`).
- Logging and diagnostic text are routed exclusively to `stderr`, leaving `stdout` purely dedicated to clean JSON-RPC protocol frames.
- Child processes should run unbuffered (`PYTHONUNBUFFERED=1` in Python).

### Standard MCP Lifecycle
1. **Spawn**: The MCP client launches the server process with piped `stdin`, `stdout`, and `stderr`.
2. **Initialize**: Client sends `{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", ...}}`.
3. **Initialized Notification**: Client sends `{"jsonrpc": "2.0", "method": "notifications/initialized"}` to confirm readiness.
4. **Tool Discovery**: Client discovers capabilities with `{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}`.
5. **Tool Execution**: Client calls tools via `{"jsonrpc": "2.0", "id": N, "method": "tools/call", "params": {"name": "...", "arguments": {...}}}`.
6. **Graceful Shutdown**: The client closes `stdin` or issues a termination signal. Servers terminate cleanly with zero dangling threads or locks.

---

## 🔍 Interactive Debugging with MCP Inspector

You can inspect, interact with, and debug both Specsynth MCP servers using the official Model Context Protocol Inspector UI:

### Inspecting the Python Server
```bash
npx @modelcontextprotocol/inspector python -m specsynth.mcp.server
```

### Inspecting the Node.js Server
```bash
npx @modelcontextprotocol/inspector node perandam-psi/mcp_server.mjs
```

### Recorded Inspector Sessions
Standard serialized Inspector session transcripts are recorded in the repository under:
- `sample_models/mcp/inspector_session_python.json` — Verified Python session transcript.
- `sample_models/mcp/inspector_session_node.json` — Verified Node.js session transcript.

These fixtures record live `initialize`, `notifications/initialized`, `tools/list`, and tool call invocations, enabling headless CI verification and offline regression benchmarking.

---

## 🧪 Automated Transport Acceptance Client

To verify stdio transport and scientific workflows out-of-process without an external agent:

```bash
# Run standalone transport client against both servers
python scripts/mcp_client_transport.py --server both

# Run automated pytest transport acceptance suite
pytest -v tests/test_mcp_transport_acceptance.py

# Run standalone P4 acceptance verification harness
python scripts/verify_p4_mcp_transport.py
```

---

## 🔒 Security & Invariants

1. **Read-Only / Sandboxed Execution**: All MCP tool endpoints operate strictly on user-specified local caches or bundled demonstration catalogs without remote socket binding by default.
2. **Loopback Isolation**: The HTTP bridge binds strictly to loopback interfaces (`127.0.0.1`, `localhost`, `::1`). Non-loopback binding (`0.0.0.0`) is prohibited unless explicitly commanded with `--allow-remote` and an authenticated token.
3. **Cross-Origin Protection**: The HTTP bridge enforces explicit origin filtering against local dev origins (`http://localhost:5173`) and denies untrusted foreign web origins.
4. **Schema Invariant Checking**: All payloads pass through versioned dataclass contracts (`specsynth.contracts`), guaranteeing that external agents receive mathematically consistent astronomical units.
