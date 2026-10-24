# Codex MCP connection

Run `qh serve` on loopback and keep the token in the environment:

```toml
[mcp_servers.qharness]
url = "http://127.0.0.1:8765/mcp"
bearer_token_env_var = "QH_LOCAL_TOKEN"
enabled_tools = ["qh_project_get", "qh_knowledge_search", "qh_task_get", "qh_report_list"]
```

Every call must include an explicit Project ID. Q-Harness exposes no coding-execution MCP tool in the MVP.

