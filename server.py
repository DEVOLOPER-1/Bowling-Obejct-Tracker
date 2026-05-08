import os
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
from flask import Flask, request, render_template, jsonify, send_from_directory

# Import the new factory
from pipelines.pipelines_wrapper import run_pipeline_factory

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
JOBS: Dict[str, Dict] = {}
EXEC = ThreadPoolExecutor(max_workers=2)


def discover_pipelines():
    """Discover python files in `pipelines/` directory (excluding wrappers/init)."""
    pipelines_dir = os.path.join(os.getcwd(), "pipelines")
    modules = []
    for fname in os.listdir(pipelines_dir):
        # Return anything that is a python script, except the factory wrapper itself
        if fname.endswith(".py") and fname not in [
            "__init__.py",
            "pipelines_wrapper.py",
        ]:
            modules.append(fname[:-3])
    return modules


def run_job(job_id, pipeline_module_name, input_a, input_b):
    job = JOBS[job_id]
    job["status"] = "running"
    try:
        out_a = os.path.join(OUTPUT_DIR, f"{job_id}_A_{pipeline_module_name}.mp4")
        out_b = os.path.join(OUTPUT_DIR, f"{job_id}_B_{pipeline_module_name}.mp4")

        # 1. Use the wrapper factory to run the pipelines safely
        res_a = run_pipeline_factory(pipeline_module_name, input_a, out_a)
        res_b = run_pipeline_factory(pipeline_module_name, input_b, out_b)

        job["status"] = "finished"
        job["result"] = {
            "pipeline": pipeline_module_name,
            "player_a": res_a,
            "player_b": res_b,
        }

        with open(os.path.join(OUTPUT_DIR, f"{job_id}_result.json"), "w") as fh:
            json.dump(job["result"], fh)

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/")
def index():
    pipelines = discover_pipelines()
    return render_template("index.html", pipelines=pipelines)


@app.route("/run", methods=["POST"])
def run():
    # expects two files: player_a, player_b and pipeline name
    pipeline_name = request.form.get("pipeline")
    if "player_a" not in request.files or "player_b" not in request.files:
        return jsonify(
            {"error": "Please upload two video files as player_a and player_b"}
        ), 400

    f_a = request.files["player_a"]
    f_b = request.files["player_b"]

    job_id = uuid.uuid4().hex[:8]
    a_path = os.path.join(UPLOAD_DIR, f"{job_id}_A_{f_a.filename}")
    b_path = os.path.join(UPLOAD_DIR, f"{job_id}_B_{f_b.filename}")
    f_a.save(a_path)
    f_b.save(b_path)

    JOBS[job_id] = {"status": "queued", "pipeline": pipeline_name}
    # schedule job
    EXEC.submit(run_job, job_id, pipeline_name, a_path, b_path)

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)


@app.route("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
