# Databricks notebook source
# MAGIC %md
# MAGIC # Build React Frontend
# MAGIC Run this notebook once on any cluster to compile the React UI into `frontend/dist/`.
# MAGIC After this cell finishes, the Databricks App can serve the built UI.

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

if not node_ok:
    print("Node not found — installing via nvm...")
    run("curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash")
    run('export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm install 20 && nvm use 20')
    node_ok = run("node --version") == 0
    print(f"Node installed: {node_ok}")

# COMMAND ----------

# MAGIC %md ## Step 3 — npm install

# COMMAND ----------

rc = run("npm install --prefer-offline --no-audit --no-fund", cwd=FRONTEND_DIR)
assert rc == 0, "npm install failed — check output above"
print("✓ npm install done")

# COMMAND ----------

# MAGIC %md ## Step 4 — npm run build

# COMMAND ----------

rc = run("npm run build", cwd=FRONTEND_DIR)
assert rc == 0, "npm run build failed — check output above"
print("✓ Build complete")

# COMMAND ----------

# Verify dist was created
dist_dir = os.path.join(FRONTEND_DIR, "dist")
files = os.listdir(dist_dir)
print(f"✓ frontend/dist/ created with {len(files)} files:")
for f in files:
    print(f"  {f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Done!
# MAGIC The React UI is built. You can now start the Databricks App — it will serve
# MAGIC the compiled files from `frontend/dist/` automatically.
