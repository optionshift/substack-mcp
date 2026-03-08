import os

from src.server import mcp, get_transport, create_starlette_app

if get_transport() == "streamable-http":
    import uvicorn

    app = create_starlette_app()
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
else:
    mcp.run(transport="stdio")
