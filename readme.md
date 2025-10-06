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
docker run -d --name dremio_mcp_client -p 8005:8000 dremio_mcp_client
python -m webbrowser http://localhost:8005
```

And to delete, run:

```bash
docker stop dremio_mcp_client
docker container rm dremio_mcp_client
docker image rm dremio_mcp_client
```

## Deploy

4) Add the two sources in Dremio
Add PostgreSQL (CRM)
In the left rail, go to Datasets → Add Source → PostgreSQL.
Name: PG_CRM
Host: pgcrm (Docker service name), Port: 5432
Database: crm, Username: crm, Password: crm_pw.
Save.
(Flow and fields match the Postgres source guide.) 
Dremio Docs
+1
Add MySQL (Billing)
Datasets → Add Source → MySQL.
Name: MYSQL_BILL
Host: mysqlbill, Port 3306
Database: billing, Username: billing, Password: billing_pw.
Save.

Here is a test query on this data:
SELECT
  c.full_name,
  c.email,
  c.state,
  SUM(i.amount_cents) / 100.0 AS lifetime_revenue_usd,
  COUNT(CASE WHEN i.status = 'paid' THEN 1 END) AS paid_invoices
FROM PG_CRM.public.customers AS c
LEFT JOIN MYSQL_BILL.billing.invoices AS i
  ON LOWER(i.customer_email) = LOWER(c.email)
GROUP BY 1,2,3
ORDER BY lifetime_revenue_usd DESC;

It can be saved as a view by clicking the PG_CRM datasource, running it, and saving it as a view. We recommend you create a space Spaces -> Add.

## Updating

## Authors

Clinton Bradford, cbradford@uidaho.edu

Based on the [IIDS Flask Cookiecutter](https://github.com/ui-iids/flask-cookiecutter)
