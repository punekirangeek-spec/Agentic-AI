from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from google import genai
import psycopg2
from flask import send_from_directory

from agent import run_agent

load_dotenv()

app = Flask(__name__)
CORS(app)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
JWT_SECRET = os.getenv("JWT_SECRET")


def get_db_connection():
    return psycopg2.connect(
        user=DB_USER, password=DB_PASSWORD,
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME
    )


# --- Auth helpers ---

def generate_token(employee_id, role):
    payload = {
        "employee_id": employee_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=8)  # token valid for 8 hours
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def token_required(f):
    """Decorator that checks for a valid JWT token before allowing the route to run."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired, please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        # Attach the decoded info to the request so the route can use it
        request.employee_id = payload["employee_id"]
        request.role = payload["role"]
        return f(*args, **kwargs)

    return decorated


# --- Routes ---

@app.route("/")
def home():
    return jsonify({"status": "Flask is running"})


@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT employee_id, full_name, password_hash, role FROM employees WHERE email = %s;",
            (email,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return jsonify({"error": "Invalid email or password"}), 401

        employee_id, full_name, password_hash, role = row

        if not bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
            return jsonify({"error": "Invalid email or password"}), 401

        token = generate_token(employee_id, role)

        return jsonify({
            "token": token,
            "employee_id": employee_id,
            "full_name": full_name,
            "role": role
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
@token_required
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message", "")

        if not user_message.strip():
            return jsonify({"error": "Empty message"}), 400

        reply, generated_filename = run_agent(
            user_message,
            employee_id=request.employee_id,
            role=request.role
        )

        response_data = {"reply": reply}
        if generated_filename:
            response_data["download_url"] = f"http://127.0.0.1:5000/download/{generated_filename}"

        return jsonify(response_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("generated_files", filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)