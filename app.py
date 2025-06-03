import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response
from werkzeug.utils import secure_filename
import sqlite3
import hashlib

# Fix: Use non-GUI backend for Matplotlib
import matplotlib
matplotlib.use("Agg")

# Flask app setup
app = Flask(__name__)
app.secret_key = "myIP"

UPLOAD_FOLDER = "static/uploads"
OUTPUT_FOLDER = "static/outputs"
ALLOWED_EXTENSIONS = {"csv"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    return render_template("home.html")

@app.route("/hiw")
def how_it_works():
    return render_template("hiw.html")


@app.route("/features")
def features():
    return render_template("features.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")



@app.route("/columns", methods=["POST"])
def get_columns():
    """Extracts column names from uploaded CSV."""
    if "csvFile" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["csvFile"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        df = pd.read_csv(filepath)

        return jsonify({"columns": df.columns.tolist()})

    return jsonify({"error": "Invalid file format"}), 400

@app.route("/upload", methods=["POST"])
def upload_file():
    """Generates a graph based on selected columns and type."""
    if "csvFile" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["csvFile"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    x_axis = request.form.get("xAxis")
    y_axis = request.form.getlist("yAxis")  # Multiple Y-axis allowed
    graph_type = request.form.get("graphType")

    if not x_axis or not y_axis or not graph_type:
        return jsonify({"error": "Please select X, Y axis and graph type"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        df = pd.read_csv(filepath)

        # Convert date columns if needed
        for col in df.select_dtypes(include=["object"]).columns:
            try:
                df[col] = pd.to_datetime(df[col])
            except ValueError:
                pass  # Ignore non-date columns

        # Ensure numeric data for Y-axis
        for col in y_axis:
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            except ValueError:
                return jsonify({"error": f"Column '{col}' is not numeric"}), 400

        # Plot settings
        plt.figure(figsize=(10, 6))
        graph_path = os.path.join(app.config["OUTPUT_FOLDER"], "graph.png")

        # Generate the selected graph type
        try:
            if graph_type == "bar":
                df.plot(x=x_axis, y=y_axis, kind="bar")
            elif graph_type == "line":
                df.plot(x=x_axis, y=y_axis, kind="line")
            elif graph_type == "scatter":
                for col in y_axis:
                    plt.scatter(df[x_axis], df[col], label=col)
                plt.xlabel(x_axis)
                plt.legend()
            elif graph_type == "heatmap":
                # Select only numeric columns for correlation matrix
                numeric_df = df.select_dtypes(include=["number"])

                if numeric_df.empty:
                    return jsonify({"error": "No numeric data available for heatmap"}), 400

                plt.figure(figsize=(10, 6))
                sns.heatmap(numeric_df.corr(), annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5)

            else:
                return jsonify({"error": "Invalid graph type"}), 400

            plt.title(f"{graph_type.capitalize()} Graph")
            plt.savefig(graph_path)
            plt.close()

            # Compute statistics
            stats = df[y_axis].describe().to_dict()

            return jsonify({"graph_url": "/static/outputs/graph.png", "stats": stats})

        except Exception as e:
            return jsonify({"error": f"Graph generation failed: {str(e)}"}), 500

    return jsonify({"error": "Invalid file format"}), 400

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_users_table():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_email" in session:
        return redirect(url_for("dashboard"))  # Redirect if already logged in

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = hash_password(password)
        
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, hashed_password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_email'] = email
            return redirect(url_for("dashboard"))
        else:
            return "Invalid email or password!", 400

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_email" in session:
        return redirect(url_for("dashboard"))  # Redirect if already logged in
    
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm-password"]
        
        if password != confirm_password:
            return "Passwords do not match!", 400
        
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        hashed_password = hash_password(password)
        
        try:
            cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed_password))
            conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Error: Email already exists!", 400
        
        conn.close()
    
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if 'user_email' not in session:
        return redirect(url_for("login"))  # Redirect to login if session is missing
    
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, email FROM users WHERE email = ?", (session['user_email'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template("dashboard.html", user=user)



@app.route("/logout")
def logout():
    session.pop('user_email', None)
    return redirect(url_for("login"))



@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    create_users_table()
    app.run(debug=True)

