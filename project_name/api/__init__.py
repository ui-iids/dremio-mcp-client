from .example import register_api
from flask import Flask


def register_apis(app: Flask):
    register_api(app)
