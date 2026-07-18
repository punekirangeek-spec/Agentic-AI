import os
import bcrypt
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
)
cur = conn.cursor()

# Set a password for each test user (change these for your own testing)
users_to_update = [
    ("aarav.sharma@example.com", "password123"),
    ("priya.nair@example.com", "password123"),
    ("HR@test.com", "password"),
]

for email, plain_password in users_to_update:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    cur.execute(
        "UPDATE employees SET password_hash = %s WHERE email = %s;",
        (hashed.decode("utf-8"), email)
    )
    print(f"Updated password for {email}")

conn.commit()
cur.close()
conn.close()
print("Done.")