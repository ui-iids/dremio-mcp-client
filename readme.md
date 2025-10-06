# dremio_mcp_client

dremio_mcp_client created by ViaJables

## Install

This package intends `uv` as its build system and package manager, but is likely compatible with `pip`.

To install the project, install `uv` through your local package manager, install script, or `pip`.

Then run

```
uv sync
```

in the root directory.

## Run

To run the project as a developer, run:

```bash
uv run flask --app dremio_mcp_client run --debug
```

To run the project as a standalone server, run:

```bash
gunicorn
```

To run the project in a container, after installing docker, run:

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
