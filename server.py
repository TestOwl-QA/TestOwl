from mcp.server import Server
from mcp.server.sse import SseServerTransport
import uvicorn

server = Server("owl")
sse = SseServerTransport("/msg")

async def app(scope, receive, send):
    if scope["type"] != "http": return
    p = scope.get("path")
    if p == "/sse": 
        await sse.connect_sse(scope, receive, send)
    elif p == "/msg" and scope.get("method") == "POST": 
        await sse.handle_post_message(scope, receive, send)
    else:
        await send({"type":"http.response.start","status":404,"headers":[]})
        await send({"type":"http.response.body","body":b""})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
