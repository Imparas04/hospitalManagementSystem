"""One consistent JSON shape for every API response.

Success: {"success": true,  "message": "...", "data": {...}}
Error:   {"success": false, "message": "...", "errors": {...}}
"""
from flask import jsonify


def success_response(message="Success", data=None, status=200):
    return jsonify({"success": True, "message": message, "data": data}), status


def error_response(message="Something went wrong", errors=None, status=400):
    return jsonify({"success": False, "message": message, "errors": errors or {}}), status
