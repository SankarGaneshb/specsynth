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

## 🔒 Security & Invariants

1. **Read-Only / Sandboxed Execution**: All MCP tool endpoints operate strictly on user-specified local caches or bundled demonstration catalogs without remote socket binding by default.
2. **Schema Invariant Checking**: All payloads pass through versioned dataclass contracts (`specsynth.contracts`), guaranteeing that external agents receive mathematically consistent astronomical units.
