import html


def login_page(
    client_name: str,
    request_id: str,
    scope: str = "Full access",
    error: str | None = None,
) -> str:
    error_html = ""
    if error:
        error_html = (
            f'<div style="background:#fef2f2;border:1px solid #fca5a5;color:#991b1b;'
            f'padding:12px;border-radius:8px;margin-bottom:16px;font-size:14px">'
            f"{html.escape(error)}</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Authorize — Substack MCP Server</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 40px;
      width: 100%;
      max-width: 420px;
      box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
    }}
    h1 {{ font-size: 20px; font-weight: 600; margin-bottom: 8px; color: #f8fafc; }}
    .subtitle {{ font-size: 14px; color: #94a3b8; margin-bottom: 24px; line-height: 1.5; }}
    .client-name {{ color: #f97316; font-weight: 500; }}
    label {{ display: block; font-size: 13px; color: #94a3b8; margin-bottom: 6px; font-weight: 500; }}
    input[type="password"] {{
      width: 100%;
      padding: 12px 16px;
      background: #0f172a;
      border: 1px solid #475569;
      border-radius: 8px;
      color: #f8fafc;
      font-size: 15px;
      outline: none;
      transition: border-color 0.2s;
    }}
    input[type="password"]:focus {{ border-color: #f97316; }}
    .actions {{ display: flex; gap: 12px; margin-top: 24px; }}
    button {{
      flex: 1;
      padding: 12px;
      border: none;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.2s;
    }}
    button:hover {{ opacity: 0.9; }}
    .btn-primary {{ background: #f97316; color: #0f172a; }}
    .btn-secondary {{ background: #334155; color: #94a3b8; }}
    .scope-info {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 20px;
      font-size: 13px;
      color: #94a3b8;
    }}
    .scope-info strong {{ color: #e2e8f0; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Authorize Access</h1>
    <p class="subtitle">
      <span class="client-name">{html.escape(client_name)}</span> wants to access your Substack MCP Server.
    </p>
    <div class="scope-info">
      <strong>Access requested:</strong> {html.escape(scope)}
    </div>
    {error_html}
    <form method="POST" action="/login">
      <input type="hidden" name="request_id" value="{html.escape(request_id)}">
      <label for="password">Server Password</label>
      <input type="password" id="password" name="password" placeholder="Enter password" autofocus required>
      <div class="actions">
        <button type="button" class="btn-secondary" onclick="window.close()">Deny</button>
        <button type="submit" class="btn-primary">Authorize</button>
      </div>
    </form>
  </div>
</body>
</html>"""
