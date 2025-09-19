from sass import compile

css = compile(filename="project_name/static/sass/style.scss", output_style="compressed")
with open("project_name/static/css/style.css", "w") as f:
    f.write(css)
