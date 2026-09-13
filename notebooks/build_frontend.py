# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Build React Frontend & Push to GitHub
# MAGIC Run this notebook once on any cluster to compile the React UI into `frontend/dist/`
# MAGIC and push it to GitHub so the Databricks App can serve it.

# COMMAND ----------

import subprocess, os

# Detect workspace repo path — works for Git Folders (Repos)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in dir() else "/Workspace/Repos"

# Try to find the actual project folder
import glob as _glob
candidates = _glob.glob("/Workspace/Repos/*/rwe_ads_platform") + \
             _glob.glob("/Workspace/Users/*/rwe_ads_platform") + \
             _glob.glob("/Workspace/Shared/rwe_ads_platform")

if candidates:
    REPO_ROOT = candidates[0]

FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
print(f"📁 Repo root   : {REPO_ROOT}")
print(f"📁 Frontend dir: {FRONTEND_DIR}")
assert os.path.isdir(FRONTEND_DIR), f"frontend/ not found at {FRONTEND_DIR}"

# COMMAND ----------

# MAGIC %md ## Step 1 — Check Node.js

# COMMAND ----------

def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout: print(r.stdout)
    if r.stderr: print(r.stderr)
    return r.returncode

node_ok = run("node --version") == 0
npm_ok  = run("npm --version")  == 0
print(f"\n✓ node: {node_ok}   ✓ npm: {npm_ok}")

# COMMAND ----------

# MAGIC %md ## Step 2 — Install Node.js if missing

# COMMAND ----------

# DBTITLE 1,Cell 6
import shutil as _shutil

if not node_ok or not npm_ok:
    print("Node/npm not fully available — installing via nodeenv...")
    _ndir = "/tmp/_nodeenv"
    rc = run(f"python -m nodeenv --node=20.18.0 --force {_ndir}")
    assert rc == 0, "nodeenv install failed — check cluster internet access"
    os.environ["PATH"] = f"{_ndir}/bin:{os.environ['PATH']}"

    node_ok = run("node --version") == 0
    npm_ok = run("npm --version") == 0
    print(f"✓ node: {node_ok}   ✓ npm: {npm_ok}")
    assert node_ok and npm_ok, "Failed to install Node.js and npm"

# COMMAND ----------

# MAGIC %md ## Step 3 — npm install

# COMMAND ----------

# DBTITLE 1,Cell 8
import shutil

# WSFS (/Workspace/) does not support rename() — npm needs it during install.
# Copy sources to /tmp (a real filesystem), run npm there.
BUILD_DIR = "/tmp/frontend_build"
if os.path.isdir(BUILD_DIR):
    shutil.rmtree(BUILD_DIR)
shutil.copytree(FRONTEND_DIR, BUILD_DIR, ignore=shutil.ignore_patterns("node_modules", "dist"))
print(f"📋 Copied frontend → {BUILD_DIR}")

rc = run("npm install --no-audit --no-fund", cwd=BUILD_DIR)
assert rc == 0, "npm install failed — check output above"
print("✓ npm install done")

# COMMAND ----------

# MAGIC %md ## Step 4 — npm run build

# COMMAND ----------

# DBTITLE 1,Cell 10
rc = run("npm run build", cwd=BUILD_DIR)
assert rc == 0, "npm run build failed — check output above"

# Copy dist/ back to workspace (overwrite in-place, no delete)
dist_src = os.path.join(BUILD_DIR, "dist")
dist_dst = os.path.join(FRONTEND_DIR, "dist")
shutil.copytree(dist_src, dist_dst, dirs_exist_ok=True)
print(f"✓ Build complete — dist/ copied to {dist_dst}")

# COMMAND ----------

# Verify dist was created
dist_dir = os.path.join(FRONTEND_DIR, "dist")
files = os.listdir(dist_dir)
print(f"✓ frontend/dist/ created with {len(files)} files:")
for f in files:
    print(f"  {f}")

# COMMAND ----------

# MAGIC %md ## Step 5 — Commit dist and push to GitHub

# COMMAND ----------

# Configure git identity
run(f'git config user.email "dr20@its.jnj.com"', cwd=REPO_ROOT)
run(f'git config user.name "DR20"', cwd=REPO_ROOT)

# Stage built dist
run("git add frontend/dist/", cwd=REPO_ROOT)
run("git add app.yaml requirements.txt", cwd=REPO_ROOT)

# Commit (ok if nothing new to commit)
r = subprocess.run(
    'git commit -m "Build: compiled React frontend dist"',
    shell=True, cwd=REPO_ROOT, capture_output=True, text=True
)
print(r.stdout or r.stderr)

# Push
rc = run("git push origin master", cwd=REPO_ROOT)
assert rc == 0, "git push failed — check Git Folder credentials in Databricks"
print("✓ Pushed dist to GitHub")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Done!
# MAGIC `frontend/dist/` is now in GitHub.
# MAGIC
# MAGIC **Next:** Go to **Databricks Apps → your app → Redeploy** to pick up the built UI.
