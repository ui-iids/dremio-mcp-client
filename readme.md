# dremio_mcp_client

**dremio_mcp_client** created by **ViaJables**

---

## 🚀 Deploy

In the `deploy_scripts` directory, there is a script called **`deploy_dremio.sh`**.

### Usage
- This script **should be run in its own directory** (do not run it inside another active project directory).  
- It requires your **Anthropic API key** to be set as the environment variable `YOUR_ANTHROPIC_API_KEY` within the script.

### Dremio Setup
Before running the script, visit the Dremio admin interface at:

👉 [http://localhost:9047](http://localhost:9047)

Follow the setup instructions to create the **admin account**.

- The default password is `dremioadmin1`.  
- If you change it, make sure to **update the password in the deploy script** accordingly.

After setup, run the Flask server as instructed by the deploy script to access the **chat interface**.

---

## 💬 Chat Interface

Once deployed, the Flask server exposes a **chat-based interface** for interacting with Dremio through the MCP bridge.

This interface allows you to:
- Send natural language queries that are converted into Dremio SQL commands.
- View structured results from Dremio’s query engine.
- Experiment with data operations using Anthropic or OpenAI-backed models for reasoning and query synthesis.

Access it locally after deployment at:

👉 [http://localhost:8005](http://localhost:8005)

---

## 🔄 Updating

To update dependencies or rebuild the environment, simply run:

```bash
uv sync
```

If using Docker, rebuild your image:

```bash
docker build -t dremio_mcp_client -f Containerfile .
```

---

Based on the [IIDS Flask Cookiecutter](https://github.com/ui-iids/flask-cookiecutter)
