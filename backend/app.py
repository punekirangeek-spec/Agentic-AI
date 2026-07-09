from flask import Flask, jsonify
from dotenv import load_dotenv
import os
from google import genai
import psycopg2

load_dotenv()

app = Flask(__name__)

# Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Postgres connection details
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

def get_db_connection():
    return psycopg2.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME
    )

@app.route("/")
def home():
    return jsonify({"status": "Flask is running"})

@app.route("/test-gemini")
def test_gemini():
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Reply with exactly: 'Connection successful'"
        )
        return jsonify({"gemini_response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test-db")
def test_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT full_name, department FROM employees;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        employees = [{"name": row[0], "department": row[1]} for row in rows]
        return jsonify({"employees": employees})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)