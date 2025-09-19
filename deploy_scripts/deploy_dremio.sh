# Use the provided key if not already in the environment
: "${ANTHROPIC_API_KEY:=YOUR_ANTHROPIC_API_KEY}"


# 0) Dremio up
docker compose up -d dremio
until curl -sf http://localhost:9047/apiv2/server_status | grep -q OK; do
  echo "Waiting for Dremio..."; sleep 5
done

# 1) Clone + deps
git clone git@github.com:ui-iids/dremio-mcp-client.git
git clone https://github.com/dremio/dremio-mcp
cd dremio-mcp-client
uv sync
source .venv/bin/activate
# 2) Token
export DREMIO_URL="http://localhost:9047"
export DREMIO_USER="admin"
export DREMIO_PASSWORD="dremioadmin1"
chmod +x ./generate_dremio_token.sh
./generate_dremio_token.sh
export DREMIO_TOKEN="$(cat .dremio_token)"
cp token.txt ../dremio-mcp/token.txt




# 3) MCP server
cd ../dremio-mcp
uv sync
source .venv/bin/activate
uv run dremio-mcp-server config create claude
uv run dremio-mcp-server config list --type dremioai
uv run dremio-mcp-server run &
SERVER_PID=$!
echo "MCP server PID: $SERVER_PID"

# 4) Flask app (adjust path/module as needed)
cd ..

MCP_DIR="$(cd dremio-mcp && pwd)"
ENV_FILE=".env"



# Create .env with strict perms and masked logging


echo "[env] Wrote $(basename "$ENV_FILE") with ANTHROPIC_API_KEY=(hidden) and DREMIO_MCP_DIR=$MCP_DIR"
cd dremio-mcp-client
source .venv/bin/activate
echo "sqlite:///database.sqlite"

export DB_URI="sqlite:///database.sqlite"
echo "[db] Using SQLite at ${DB_PATH}"
umask 177
{
  printf "ANTHROPIC_API_KEY=%s\n" "$ANTHROPIC_API_KEY"
  printf "DREMIO_MCP_DIR=%s\n" "$MCP_DIR"
  PRINTF "DB_URI=%s\n" "$DB_URI"
} > "$ENV_FILE"

printf "RUN FLASK IN THE dremio-mcp-client directory via: uv run flask --app dremio_mcp_client run --debug"


