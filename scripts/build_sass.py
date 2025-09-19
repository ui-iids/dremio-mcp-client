from sass import compile

css = compile(filename="dremio_mcp_client/static/sass/style.scss", output_style="compressed")
with open("dremio_mcp_client/static/css/style.css", "w") as f:
    f.write(css)
