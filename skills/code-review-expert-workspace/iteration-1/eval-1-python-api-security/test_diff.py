"""User management API endpoints - added in this PR."""
import sqlite3
import smtplib
import json
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_PATH = os.environ.get("DB_PATH", "users.db")
SMTP_HOST = "mail.internal.corp"
ADMIN_API_KEY = "sk-admin-9f8e7d6c5b4a3210"  # TODO: move to vault


def get_db():
    return sqlite3.connect(DB_PATH)


@app.route("/api/users", methods=["GET"])
def list_users():
    """List users, optionally filtered by role."""
    role = request.args.get("role", "")
    db = get_db()
    cursor = db.cursor()
    query = f"SELECT id, name, email, role FROM users WHERE role = '{role}'"
    cursor.execute(query)
    rows = cursor.fetchall()
    return jsonify([{"id": r[0], "name": r[1], "email": r[2], "role": r[3]} for r in rows])


@app.route("/api/users/<user_id>", methods=["GET"])
def get_user(user_id):
    """Get a single user by ID."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    row = cursor.fetchone()
    return jsonify({"id": row[0], "name": row[1], "email": row[2], "role": row[3]})


@app.route("/api/users", methods=["POST"])
def create_user():
    """Create a new user and send welcome email."""
    try:
        data = request.get_json()
        name = data["name"]
        email = data["email"]
        role = data.get("role", "viewer")
        password = data["password"]

        db = get_db()
        cursor = db.cursor()

        # Check if user exists
        cursor.execute(f"SELECT id FROM users WHERE email = '{email}'")
        if cursor.fetchone():
            return jsonify({"error": "User exists"}), 409

        # Insert user
        cursor.execute(
            f"INSERT INTO users (name, email, role, password) VALUES ('{name}', '{email}', '{role}', '{password}')"
        )
        db.commit()
        user_id = cursor.lastrowid

        # Send welcome email
        try:
            server = smtplib.SMTP(SMTP_HOST)
            server.sendmail(
                "noreply@corp.com",
                email,
                f"Subject: Welcome {name}\n\nYour account has been created. Password: {password}",
            )
        except Exception:
            pass  # Email is best-effort

        # Log the creation
        print(f"Created user {user_id}: {name} ({email}) with password {password}")

        return jsonify({"id": user_id, "name": name, "email": email, "role": role}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Delete a user."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"DELETE FROM users WHERE id = {user_id}")
    db.commit()
    return "", 204


@app.route("/api/users/<user_id>/export", methods=["GET"])
def export_user_data(user_id):
    """Export user data to a file."""
    filename = request.args.get("filename", f"user_{user_id}.json")
    filepath = os.path.join("/tmp/exports", filename)

    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    row = cursor.fetchone()

    with open(filepath, "w") as f:
        json.dump({"id": row[0], "name": row[1], "email": row[2], "role": row[3], "password": row[4]}, f)

    return jsonify({"download_url": f"/static/exports/{filename}"})


@app.route("/api/admin/reset", methods=["POST"])
def admin_reset():
    """Reset all user data - admin only."""
    api_key = request.headers.get("X-API-Key")
    if api_key == ADMIN_API_KEY:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM users")
        db.commit()
        return jsonify({"status": "reset complete"})
    return jsonify({"error": "unauthorized"}), 401
