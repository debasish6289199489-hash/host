from flask import Flask, request, render_template_string, redirect, url_for, make_response
import os
import threading
import time
import requests
import subprocess
import json
import shutil
import traceback
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuration for Render
UPLOAD_FOLDER = "user_files"
LOGS_FOLDER = "logs"
USERS_FILE = "users.json"
REPO_DIR = "private_repo"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOGS_FOLDER, exist_ok=True)

# Global dictionary to track running processes
running_processes = {}

# Security functions
def allowed_file(filename):
    return True

def is_file_content_safe(file_content):
    return True

# User management
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

users = load_users()

def get_user_folder(username):
    folder = os.path.join(UPLOAD_FOLDER, username)
    os.makedirs(folder, exist_ok=True)
    return folder

def get_user_log_folder(username):
    folder = os.path.join(LOGS_FOLDER, username)
    os.makedirs(folder, exist_ok=True)
    return folder

# GitHub integration (optional - remove if not needed)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
REPO_URL = f"https://{GITHUB_TOKEN}:x-oauth-basic@github.com//.git" if GITHUB_TOKEN else ""

def clone_private_repo():
    if GITHUB_TOKEN and not os.path.exists(REPO_DIR):
        git_path = shutil.which("git")
        if not git_path:
            print("Git executable not found. Skipping repository clone.")
            return
        result = subprocess.run([git_path, "clone", REPO_URL, REPO_DIR])
        if result.returncode != 0:
            print("Failed to clone private repository.")

if GITHUB_TOKEN:
    clone_private_repo()

def commit_and_push(commit_message):
    if not GITHUB_TOKEN:
        return
    git_path = shutil.which("git")
    if not git_path:
        print("Git executable not found. Skipping commit and push.")
        return
    try:
        subprocess.run([git_path, "-C", REPO_DIR, "add", "."], check=True)
        subprocess.run([git_path, "-C", REPO_DIR, "commit", "-m", commit_message], check=True)
        subprocess.run([git_path, "-C", REPO_DIR, "push"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Git commit/push failed: {e}")

def sync_file_to_repo(src_path, relative_path):
    if not GITHUB_TOKEN:
        return
    dest_path = os.path.join(REPO_DIR, relative_path)
    dest_folder = os.path.dirname(dest_path)
    os.makedirs(dest_folder, exist_ok=True)
    shutil.copy(src_path, dest_path)

def delete_file_from_repo(relative_path):
    if not GITHUB_TOKEN:
        return
    repo_file = os.path.join(REPO_DIR, relative_path)
    if os.path.exists(repo_file):
        os.remove(repo_file)

# HTML Templates
login_template = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login</title>
  <style>
    body { font-family: Arial, sans-serif; background: #000; color: #00ffcc; text-align: center; padding: 10px; margin: 0; }
    .container { width: 90%; max-width: 300px; margin: 20px auto; padding: 20px; background: #111; border-radius: 10px; }
    .password-container { position: relative; display: flex; align-items: center; }
    .password-container input { flex: 1; padding-right: 50px; height: 40px; background: #222; color: #00ffcc; border: none; border-radius: 5px; }
    .password-container .toggle-btn { position: absolute; right: 0; top: 0; height: 40px; width: 50px; background: #00ffcc; border: none; cursor: pointer; font-weight: bold; display: flex; align-items: center; justify-content: center; border-radius: 0 5px 5px 0; }
    input, button { margin: 5px 0; padding: 10px; width: 100%; box-sizing: border-box; border: none; border-radius: 5px; }
    input { background: #222; color: #00ffcc; }
    button { background: #00ffcc; color: #000; font-weight: bold; cursor: pointer; }
    button:hover { background: #00cc99; }
    a { color: #00ffcc; text-decoration: none; }
    .error { color: red; margin-top: 5px; }
    @media (max-width: 600px) { .container { width: 90%; } }
  </style>
  <script>
    function togglePasswordVisibility(id, btnId) {
      var input = document.getElementById(id);
      var btn = document.getElementById(btnId);
      if (input.type === "password") {
        input.type = "text";
        btn.textContent = "Hide";
      } else {
        input.type = "password";
        btn.textContent = "Show";
      }
    }
  </script>
</head>
<body>
  <div class="container">
    <h2>Login</h2>
    <form method="post">
      <input type="text" name="username" placeholder="Username" required>
      <div class="password-container">
        <input type="password" name="password" id="password" placeholder="Password" required>
        <button type="button" id="togglePassword" class="toggle-btn" onclick="togglePasswordVisibility('password','togglePassword')">Show</button>
      </div>
      {% if error %}
        <div class="error">{{ error }}</div>
      {% endif %}
      <button type="submit">Login</button>
    </form>
    <p>Don't have an account? <a href="{{ url_for('register') }}">Register here</a></p>
  </div>
</body>
</html>
"""

register_template = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Register</title>
  <style>
    body { font-family: Arial, sans-serif; background: #000; color: #00ffcc; text-align: center; padding: 10px; margin: 0; }
    .container { width: 90%; max-width: 300px; margin: 20px auto; padding: 20px; background: #111; border-radius: 10px; }
    .password-container { position: relative; display: flex; align-items: center; }
    .password-container input { flex: 1; padding-right: 50px; height: 40px; background: #222; color: #00ffcc; border: none; border-radius: 5px; }
    .password-container .toggle-btn { position: absolute; right: 0; top: 0; height: 40px; width: 50px; background: #00ffcc; border: none; cursor: pointer; font-weight: bold; display: flex; align-items: center; justify-content: center; border-radius: 0 5px 5px 0; }
    input, button { margin: 5px 0; padding: 10px; width: 100%; box-sizing: border-box; border: none; border-radius: 5px; }
    input { background: #222; color: #00ffcc; }
    button { background: #00ffcc; color: #000; font-weight: bold; cursor: pointer; }
    button:hover { background: #00cc99; }
    a { color: #00ffcc; text-decoration: none; }
    .error { color: red; margin-top: 5px; }
    @media (max-width: 600px) { .container { width: 90%; } }
  </style>
  <script>
    function togglePasswordVisibility(id, btnId) {
      var input = document.getElementById(id);
      var btn = document.getElementById(btnId);
      if (input.type === "password") {
        input.type = "text";
        btn.textContent = "Hide";
      } else {
        input.type = "password";
        btn.textContent = "Show";
      }
    }
  </script>
</head>
<body>
  <div class="container">
    <h2>Register</h2>
    <form method="post">
      <input type="text" name="username" id="regUsername" placeholder="Username" required>
      <div class="password-container">
        <input type="password" name="password" id="regPassword" placeholder="Password" required>
        <button type="button" class="toggle-btn" id="toggleRegPassword" onclick="togglePasswordVisibility('regPassword', 'toggleRegPassword')">Show</button>
      </div>
      <div class="password-container">
        <input type="password" name="confirm_password" id="confirmRegPassword" placeholder="Confirm Password" required>
        <button type="button" class="toggle-btn" id="toggleConfirmRegPassword" onclick="togglePasswordVisibility('confirmRegPassword', 'toggleConfirmRegPassword')">Show</button>
      </div>
      {% if error %}
        <div class="error">{{ error }}</div>
      {% endif %}
      <button type="submit">Register</button>
    </form>
    <p>Already have an account? <a href="{{ url_for('login') }}">Login here</a></p>
  </div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ＨＡＰＰＹ ＣＯＤＥＲＺ ＴＥＡＭ File Hosting</title>
  <style>
    body {
      background: #000;
      color: #00ffcc;
      margin: 0;
      padding: 10px;
      font-family: Arial, sans-serif;
    }
    .active-files-screen {
      width: 90%;
      max-width: 600px;
      background: #000;
      border-radius: 10px;
      padding: 15px;
      font-size: 18px;
      margin: 10px auto;
      border: 2px solid #00ffcc;
      text-align: center;
    }
    input, button, select {
      display: block;
      margin: 10px auto;
      padding: 15px;
      font-size: 18px;
      border: none;
      border-radius: 5px;
    }
    select, input[type="file"], input[type="password"], input[type="text"] {
      width: 80%;
      background: #333;
      color: white;
    }
    button {
      background: #00ffcc;
      color: black;
      font-weight: bold;
      cursor: pointer;
      width: 250px;
    }
    button:hover {
      background: #00cc99;
    }
    #outputPanel, #activeFilePanel {
      margin: 20px auto;
      width: 90%;
      max-width: 600px;
      border: 2px solid #00ffcc;
      background: #111;
      font-size: 1em;
      overflow-y: auto;
      padding: 10px;
      border-radius: 10px;
    }
    #activeFilePanel {
      text-align: center;
    }
    #outputPanel {
      height: 100px;
      text-align: left;
    }
    .footer {
      margin-top: 30px;
      font-size: 14px;
      color: #bbb;
      text-align: center;
    }
    .pip-section {
      margin: 20px auto;
      width: 90%;
      max-width: 600px;
      border: 2px solid #00ffcc;
      background: #111;
      padding: 15px;
      border-radius: 10px;
    }
    .pip-controls {
      display: flex;
      justify-content: center;
      gap: 10px;
      margin: 10px 0;
    }
    .pip-controls button {
      width: 150px;
    }
    #pipLogs {
      height: 200px;
      overflow-y: auto;
      background: #000;
      color: #00ffcc;
      padding: 10px;
      border-radius: 5px;
      margin-top: 10px;
      text-align: left;
      font-family: monospace;
    }
    @media (max-width: 600px) {
      input, button, select { width: 90%; }
      .pip-controls { flex-direction: column; }
      .pip-controls button { width: 90%; }
    }
  </style>
</head>
<body>
  <div class="active-files-screen">
    <p style="text-align:right;">
      Logged in as <strong>{{ username }}</strong>
      | <a href="{{ url_for('logout') }}" style="color:#00ffcc;">Logout</a>
    </p>
    <h2>Active Files</h2>
    <div id="activeFilePanel">
      <pre id="active-file-screen" style="margin:0;">No active files.</pre>
    </div>
    <hr>
    <h2>📤 Upload Your File</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
      <input type="file" name="file_upload" required>
      <button type="submit">Upload</button>
    </form>
    {% if not files %}
    <form method="post">
      <button name="action" value="create_file">📄 Create File</button>
    </form>
    {% endif %}
    {% if message %}
      <p style="color: {% if '❌' in message %}red{% else %}green{% endif %};">{{ message }}</p>
    {% endif %}
    {% if files %}
      <div id="outputPanel">
        <strong></strong>
        <pre id="error-screen" style="margin:0;"></pre>
      </div>
      <button type="button" id="copyButton" style="width:250px;">Copy Log</button>
      <h3>📝 Your Uploaded Files:</h3>
      <form method="post">
        <select name="file_name">
          {% for file in files %}
            <option value="{{ file }}">{{ file }}</option>
          {% endfor %}
        </select>
        <button name="action" value="start">▶ Run File</button>
        <button name="action" value="stop">⏹ Stop File</button>
        <button name="action" value="restart">🔄 Restart File</button>
        <input type="text" name="new_file_name" placeholder="Enter new file name">
        <button name="action" value="edit_name">✏️ Edit File Name</button>
        <button name="action" value="edit_file">📝 Edit File</button>
        <button name="action" value="delete">🗑️ Delete File</button>
        <button name="action" value="create_file">📄 Create File</button>
      </form>
    {% endif %}
    
    <!-- New Pip Package Installation Section -->
    <div class="pip-section">
      <h2>📦 Install Python Packages</h2>
      <div class="pip-controls">
        <button type="button" id="togglePipSection">Install Package 📦</button>
      </div>
      <div id="pipSection" style="display: none;">
        <input type="text" id="packageName" placeholder="Enter package name (e.g., requests)" style="width: 80%;">
        <div class="pip-controls">
          <button type="button" id="installPackage">Install ✅</button>
          <button type="button" id="uninstallPackage">Uninstall 🗑️</button>
        </div>
        <div id="pipLogs">Package installation logs will appear here...</div>
      </div>
    </div>
  </div>
  <p class="footer">©HAPPY CODERZ TEAM - All Rights Reserved</p>
  <script>
  document.addEventListener("DOMContentLoaded", function(){
      var select = document.querySelector("select[name='file_name']");
      var errorScreen = document.getElementById("error-screen");
      var activeFileScreen = document.getElementById("active-file-screen");

      if (select && localStorage.getItem("selectedFile")) {
          var saved = localStorage.getItem("selectedFile");
          for (var i = 0; i < select.options.length; i++) {
              if (select.options[i].value === saved) {
                  select.selectedIndex = i;
                  break;
              }
          }
      }

      if (select) {
          select.addEventListener("change", function() {
              localStorage.setItem("selectedFile", select.value);
              updateLogs();
          });
      }

      function updateLogs() {
          if (select && select.value) {
              fetch("/get_logs?file_name=" + select.value)
              .then(response => response.text())
              .then(data => { errorScreen.textContent = data; });
          }
      }
      function updateActiveFiles() {
          fetch("/get_active_files")
          .then(response => response.text())
          .then(data => { activeFileScreen.textContent = data; });
      }
      if (select) { updateLogs(); }
      updateActiveFiles();
      setInterval(updateLogs, 1000);
      setInterval(updateActiveFiles, 1000);

      var copyBtn = document.getElementById("copyButton");
      if (copyBtn) {
          copyBtn.addEventListener("click", function(){
              var logText = document.getElementById("error-screen").innerText;
              navigator.clipboard.writeText(logText).then(function(){
                  alert("Log copied to clipboard!");
              }).catch(function(err){
                  alert("Failed to copy log: " + err);
              });
          });
      }

      // Pip Package Installation Functionality
      var togglePipBtn = document.getElementById("togglePipSection");
      var pipSection = document.getElementById("pipSection");
      var installBtn = document.getElementById("installPackage");
      var uninstallBtn = document.getElementById("uninstallPackage");
      var packageInput = document.getElementById("packageName");
      var pipLogs = document.getElementById("pipLogs");

      togglePipBtn.addEventListener("click", function() {
          if (pipSection.style.display === "none") {
              pipSection.style.display = "block";
              togglePipBtn.textContent = "Hide Package Installer";
          } else {
              pipSection.style.display = "none";
              togglePipBtn.textContent = "Install Package 📦";
          }
      });

      function updatePipLogs() {
          fetch("/get_pip_logs")
          .then(response => response.text())
          .then(data => { pipLogs.textContent = data; });
      }

      installBtn.addEventListener("click", function() {
          var packageName = packageInput.value.trim();
          if (!packageName) {
              alert("Please enter a package name!");
              return;
          }
          fetch("/install_package", {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: "package_name=" + encodeURIComponent(packageName) + "&action=install"
          })
          .then(response => response.text())
          .then(data => {
              pipLogs.textContent = data;
              // Start updating logs
              setTimeout(updatePipLogs, 1000);
          });
      });

      uninstallBtn.addEventListener("click", function() {
          var packageName = packageInput.value.trim();
          if (!packageName) {
              alert("Please enter a package name!");
              return;
          }
          fetch("/install_package", {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: "package_name=" + encodeURIComponent(packageName) + "&action=uninstall"
          })
          .then(response => response.text())
          .then(data => {
              pipLogs.textContent = data;
              // Start updating logs
              setTimeout(updatePipLogs, 1000);
          });
      });

      // Initial update of pip logs
      updatePipLogs();
  });
  </script>
</body>
</html>
"""

# Authentication Routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.cookies.get("username"):
        return redirect(url_for("hosting_page"))
    error = ""
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        if username in users and users[username] == password:
            response = make_response(redirect(url_for("hosting_page")))
            response.set_cookie("username", username, max_age=30*24*60*60, samesite="Lax", httponly=True, secure=True)
            return response
        else:
            error = "Invalid username or password."
    return render_template_string(login_template, error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.cookies.get("username"):
        return redirect(url_for("hosting_page"))
    error = ""
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        if password != confirm_password:
            error = "Passwords do not match."
        elif username in users:
            error = "Username already exists."
        else:
            users[username] = password
            save_users(users)
            if GITHUB_TOKEN:
                sync_file_to_repo(USERS_FILE, "users.json")
                commit_and_push(f"User registered: {username}")
            response = make_response(redirect(url_for("hosting_page")))
            response.set_cookie("username", username, max_age=30*24*60*60, samesite="Lax", httponly=True, secure=True)
            return response
    return render_template_string(register_template, error=error)

@app.route("/logout")
def logout():
    response = make_response(redirect(url_for("login")))
    response.delete_cookie("username")
    return response

# Main Hosting Page and Actions
@app.route("/", methods=["GET", "POST"])
def hosting_page():
    username = request.cookies.get("username")
    if not username:
        return redirect(url_for("login"))
    message = request.args.get("msg", "")
    
    if request.method == "POST":
        if "action" in request.form:
            file_name = secure_filename(request.form.get("file_name") or "")
            action = request.form.get("action")
            if action in ["start", "restart"]:
                message = start_reset_file(username, file_name)
            elif action == "stop":
                message = stop_file(username, file_name)
            elif action == "edit_name":
                new_file_name = request.form.get("new_file_name")
                if not new_file_name:
                    message = "❌ New file name required!"
                else:
                    old_path = find_file_path(username, file_name)
                    if old_path:
                        new_safe_name = secure_filename(new_file_name)
                        new_path = os.path.join(os.path.dirname(old_path), new_safe_name)
                        os.rename(old_path, new_path)
                        old_key = f"{username}:{file_name}"
                        new_key = f"{username}:{new_safe_name}"
                        if old_key in running_processes:
                            running_processes[new_key] = running_processes.pop(old_key)
                        if GITHUB_TOKEN:
                            repo_relative_path = os.path.join("user_files", username, new_safe_name)
                            sync_file_to_repo(new_path, repo_relative_path)
                            commit_and_push(f"User {username} renamed file {file_name} to {new_safe_name}")
                        message = f"✅ File renamed to {new_safe_name}!"
                    else:
                        message = "❌ File not found!"
            elif action == "edit_file":
                return redirect(url_for("edit_file", file_name=file_name))
            elif action == "delete":
                stop_file(username, file_name)
                file_path = find_file_path(username, file_name)
                if file_path:
                    try:
                        os.remove(file_path)
                        if GITHUB_TOKEN:
                            repo_relative_path = os.path.join("user_files", username, file_name)
                            delete_file_from_repo(repo_relative_path)
                            commit_and_push(f"User {username} deleted file {file_name}")
                        message = "✅ File deleted successfully!"
                    except Exception as e:
                        message = f"❌ Error deleting file: {e}"
                else:
                    message = "❌ File not found!"
            elif action == "create_file":
                return redirect(url_for("create_file"))
    
    files = []
    user_folder = get_user_folder(username)
    if os.path.exists(user_folder):
        files = sorted(os.listdir(user_folder))
    active_files = get_active_files(username)
    
    return render_template_string(HTML_TEMPLATE,
                                  username=username,
                                  files=files,
                                  message=message,
                                  active_files=", ".join(active_files))

@app.route("/upload", methods=["POST"])
def upload_file():
    username = request.cookies.get("username")
    if not username:
        return redirect(url_for("login"))
    file = request.files.get("file_upload")
    if file and allowed_file(file.filename):
        try:
            content = file.read().decode('utf-8', errors='ignore')
        except Exception as e:
            return "### ❌ Error reading file content."
        if not is_file_content_safe(content):
            return "### ❌ Uploaded file contains dangerous code!"
        file.seek(0)
        filename = secure_filename(file.filename)
        user_folder = get_user_folder(username)
        file_path = os.path.join(user_folder, filename)
        file.save(file_path)
        if GITHUB_TOKEN:
            repo_relative_path = os.path.join("user_files", username, filename)
            sync_file_to_repo(file_path, repo_relative_path)
            commit_and_push(f"User {username} uploaded file {filename}")
        return redirect(url_for("hosting_page"))
    return "### ❌ File upload failed!"

def find_file_path(username, file_name):
    user_folder = get_user_folder(username)
    safe_file_name = secure_filename(file_name)
    candidate = os.path.join(user_folder, safe_file_name)
    if os.path.commonpath([os.path.realpath(candidate), os.path.realpath(user_folder)]) != os.path.realpath(user_folder):
        return None
    if os.path.exists(candidate):
        return candidate
    return None

# File Process Management
def start_file(username, file_name):
    file_path = find_file_path(username, file_name)
    if file_path:
        log_folder = get_user_log_folder(username)
        log_file = os.path.join(log_folder, f"{secure_filename(file_name)}.log")
        open(log_file, "w").close()
        log_fd = open(log_file, "a")
        if file_path.endswith('.py'):
            proc = subprocess.Popen(["python3", "-u", file_path], stdout=log_fd, stderr=subprocess.STDOUT)
        else:
            os.chmod(file_path, 0o755)
            proc = subprocess.Popen(file_path, shell=True, stdout=log_fd, stderr=subprocess.STDOUT)
        running_processes[f"{username}:{file_name}"] = proc
        return "✅ File started successfully!"
    return "❌ File not found!"

def stop_file(username, file_name):
    key = f"{username}:{file_name}"
    proc = running_processes.get(key)
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            time.sleep(1)
            if proc.poll() is None:
                proc.kill()
        except Exception as e:
            return f"❌ Error stopping file: {e}"
        running_processes.pop(key, None)
        return "✅ File stopped!"
    return "File was not running."

def start_reset_file(username, file_name):
    stop_file(username, file_name)
    log_folder = get_user_log_folder(username)
    log_file = os.path.join(log_folder, f"{secure_filename(file_name)}.log")
    open(log_file, "w").close()
    return start_file(username, file_name)

def get_active_files(username):
    active = []
    for key, proc in list(running_processes.items()):
        user, file = key.split(":", 1)
        if user == username and proc.poll() is None:
            active.append(file)
        elif user == username:
            running_processes.pop(key, None)
    return active

@app.route("/get_logs")
def get_logs_route():
    username = request.cookies.get("username")
    if not username:
        return "Not authorized", 401
    file_name = request.args.get("file_name")
    log_folder = get_user_log_folder(username)
    log_file = os.path.join(log_folder, f"{secure_filename(file_name)}.log")
    content = ""
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            content = f.read()
    if not content:
        content = "No logs available."
    return content, 200, {'Content-Type': 'text/plain'}

@app.route("/get_active_files")
def get_active_files_route():
    username = request.cookies.get("username")
    if not username:
        return "Not authorized", 401
    active = get_active_files(username)
    output = "\n".join(active) if active else "No active files."
    return output, 200, {'Content-Type': 'text/plain'}

# Pip Package Management
PIP_LOG_FILE = "pip_installation.log"

def write_pip_log(message):
    with open(PIP_LOG_FILE, "a") as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")

@app.route("/install_package", methods=["POST"])
def install_package():
    username = request.cookies.get("username")
    if not username:
        return "Not authorized", 401
    
    package_name = request.form.get("package_name", "").strip()
    action = request.form.get("action", "install")
    
    if not package_name:
        return "❌ Package name is required!"
    
    # Clear previous log
    open(PIP_LOG_FILE, "w").close()
    
    try:
        if action == "install":
            write_pip_log(f"Starting installation of package: {package_name}")
            result = subprocess.run(
                ["pip", "install", package_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
        else:  # uninstall
            write_pip_log(f"Starting uninstallation of package: {package_name}")
            result = subprocess.run(
                ["pip", "uninstall", "-y", package_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
        
        # Write output to log
        write_pip_log(f"STDOUT:\n{result.stdout}")
        write_pip_log(f"STDERR:\n{result.stderr}")
        write_pip_log(f"Return code: {result.returncode}")
        
        if result.returncode == 0:
            if action == "install":
                return f"✅ Package '{package_name}' installed successfully!\n\nOutput:\n{result.stdout}"
            else:
                return f"✅ Package '{package_name}' uninstalled successfully!\n\nOutput:\n{result.stdout}"
        else:
            if action == "install":
                return f"❌ Failed to install package '{package_name}'\n\nError:\n{result.stderr}"
            else:
                return f"❌ Failed to uninstall package '{package_name}'\n\nError:\n{result.stderr}"
                
    except subprocess.TimeoutExpired:
        write_pip_log(f"❌ {action.capitalize()} process timed out for package: {package_name}")
        return f"❌ {action.capitalize()} process timed out for package '{package_name}'. Please try again."
    except Exception as e:
        write_pip_log(f"❌ Error during {action}: {str(e)}")
        return f"❌ Error during {action}: {str(e)}"

@app.route("/get_pip_logs")
def get_pip_logs():
    username = request.cookies.get("username")
    if not username:
        return "Not authorized", 401
    
    content = ""
    if os.path.exists(PIP_LOG_FILE):
        with open(PIP_LOG_FILE, "r") as f:
            content = f.read()
    if not content:
        content = "No pip installation logs available."
    return content, 200, {'Content-Type': 'text/plain'}

@app.route("/edit_file", methods=["GET", "POST"])
def edit_file():
    username = request.cookies.get("username")
    if not username:
        return redirect(url_for("login"))
    if request.method == "GET":
        file_name = secure_filename(request.args.get("file_name"))
    else:
        file_name = secure_filename(request.form.get("file_name"))
    file_path = find_file_path(username, file_name)
    if not file_path:
        return "❌ File not found!", 404
    if request.method == "GET":
        try:
            with open(file_path, "r") as f:
                content = f.read()
        except Exception as e:
            content = f"Error reading file: {e}"
        edit_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Edit File</title>
          <style>
          body {
              background: #000;
              color: #00ffcc;
              font-family: Arial, sans-serif;
              text-align: center;
              padding: 20px;
          }
          textarea {
              width: 80%;
              height: 800px;
              margin: 20px auto;
              padding: 10px;
              font-size: 16px;
              background: #111;
              color: #00ffcc;
              border: 2px solid #00ffcc;
              border-radius: 5px;
          }
          input[type="submit"] {
              padding: 10px 20px;
              font-size: 18px;
              background: #00ffcc;
              color: black;
              border: none;
              border-radius: 5px;
              cursor: pointer;
          }
          input[type="submit"]:hover {
              background: #00cc99;
          }
          a {
              color: #00ffcc;
          }
          @media (max-width: 600px) {
              textarea { width: 90%; }
          }
          </style>
        </head>
        <body>
        <h2>Edit File: {{ file_name }}</h2>
        <form method="post">
            <textarea name="content">{{ content }}</textarea><br>
            <input type="hidden" name="file_name" value="{{ file_name }}">
            <input type="submit" value="Save Changes">
        </form>
        <a href="{{ url_for('hosting_page') }}">Back to Hosting</a>
        </body>
        </html>
"""
        return render_template_string(edit_template, file_name=file_name, content=content)
    else:
        new_content = request.form.get("content")
        try:
            with open(file_path, "w") as f:
                f.write(new_content)
            if GITHUB_TOKEN:
                repo_relative_path = os.path.join("user_files", username, file_name)
                sync_file_to_repo(file_path, repo_relative_path)
                commit_and_push(f"User {username} updated file {file_name}")
            msg = "✅ File updated successfully!"
        except Exception as e:
            msg = f"❌ Error updating file: {e}"
        return redirect(url_for("hosting_page", msg=msg))

@app.route("/create_file", methods=["GET", "POST"])
def create_file():
    username = request.cookies.get("username")
    if not username:
        return redirect(url_for("login"))
    if request.method == "GET":
        create_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Create File</title>
          <style>
          body {
              background: #000;
              color: #00ffcc;
              font-family: Arial, sans-serif;
              text-align: center;
              padding: 20px;
          }
          input, textarea {
              width: 80%;
              margin: 10px auto;
              padding: 10px;
              font-size: 16px;
              background: #111;
              color: #00ffcc;
              border: 2px solid #00ffcc;
              border-radius: 5px;
          }
          textarea {
              height: 500px;
          }
          input[type="submit"] {
              padding: 10px 20px;
              font-size: 18px;
              background: #00ffcc;
              color: black;
              border: none;
              border-radius: 5px;
              cursor: pointer;
          }
          input[type="submit"]:hover {
              background: #00cc99;
          }
          a {
              color: #00ffcc;
          }
          @media (max-width: 600px) {
              input, textarea { width: 90%; }
          }
          </style>
        </head>
        <body>
        <h2>Create New File</h2>
        <form method="post">
            <input type="text" name="file_name" placeholder="File Name" required><br>
            <textarea name="content" placeholder="File Content"></textarea><br>
            <input type="submit" value="Create File">
        </form>
        <a href="{{ url_for('hosting_page') }}">Back to Hosting</a>
        </body>
        </html>
"""
        return render_template_string(create_template)
    else:
        file_name = secure_filename(request.form.get("file_name"))
        content = request.form.get("content", "")
        user_folder = get_user_folder(username)
        file_path = os.path.join(user_folder, file_name)
        try:
            with open(file_path, "w") as f:
                f.write(content)
            if GITHUB_TOKEN:
                repo_relative_path = os.path.join("user_files", username, file_name)
                sync_file_to_repo(file_path, repo_relative_path)
                commit_and_push(f"User {username} created file {file_name}")
            msg = "✅ File created successfully!"
        except Exception as e:
            msg = f"❌ Error creating file: {e}"
        return redirect(url_for("hosting_page", msg=msg))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
