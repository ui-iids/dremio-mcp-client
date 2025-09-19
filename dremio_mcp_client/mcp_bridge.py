import asyncio
import os
import threading

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


class MCPBridge:
    """Keeps a persistent MCP session in a background event loop."""

    def __init__(self, server_params: StdioServerParameters):
        self.server_params = server_params
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

        # Hold context managers so they don’t get GC’d/closed
        self._stdio_cm = None
        self._session_cm = None

        self.read = None
        self.write = None
        self.session: ClientSession | None = None

        # LLM client (instance!)
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

    async def _aconnect(self):
        # stdio_client is an async context manager
        self._stdio_cm = stdio_client(self.server_params)
        self.read, self.write = await self._stdio_cm.__aenter__()

        self._session_cm = ClientSession(self.read, self.write)
        self.session = await self._session_cm.__aenter__()
        await self.session.initialize()

        # quick sanity check
        await self.session.list_tools()

    def connect(self):
        fut = asyncio.run_coroutine_threadsafe(self._aconnect(), self.loop)
        fut.result(timeout=30)

    def run_coro(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout=120)

    async def _alist_tools(self):
        resp = await self.session.list_tools()
        return [
            {"name": t.name, "description": t.description, "schema": t.inputSchema}
            for t in resp.tools
        ]

    def list_tools(self):
        return self.run_coro(self._alist_tools())

    async def _aprocess_query(self, user_text: str) -> dict:
        # 1) Advertise tools to the LLM
        tools_resp = await self.session.list_tools()
        tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            }
            for t in tools_resp.tools
        ]

        messages = [{"role": "user", "content": user_text}]
        trace = []

        while True:
            resp = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=messages,
                tools=tools,
            )

            tool_uses = [
                c for c in resp.content if getattr(c, "type", None) == "tool_use"
            ]
            texts = [c.text for c in resp.content if getattr(c, "type", None) == "text"]
            if texts:
                trace.append({"assistant_text": "\n".join(texts)})

            if not tool_uses:
                return {"answer": "\n".join(texts) if texts else "", "trace": trace}

            tool_results_content = []
            for tu in tool_uses:
                # Execute tool via MCP
                result = await self.session.call_tool(tu.name, tu.input)
                tool_results_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": result.content,
                    }
                )
                trace.append(
                    {"tool_called": tu.name, "args": tu.input, "result": result.content}
                )

            # continue the tool loop
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": tool_results_content})

    def process_query(self, user_text: str) -> dict:
        return self.run_coro(self._aprocess_query(user_text))

    async def _aclose(self):
        # Close in reverse order
        if self._session_cm:
            await self._session_cm.__aexit__(None, None, None)
            self._session_cm = None
            self.session = None
        if self._stdio_cm:
            await self._stdio_cm.__aexit__(None, None, None)
            self._stdio_cm = None
            self.read = self.write = None

    def close(self):
        try:
            self.run_coro(self._aclose())
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=2)
