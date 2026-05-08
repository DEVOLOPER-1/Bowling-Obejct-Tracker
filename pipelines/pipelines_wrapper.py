# pipelines/pipelines_wrapper.py
import os
import subprocess
import json


def run_pipeline_factory(pipeline_name: str, input_path: str, output_path: str) -> dict:
    """
    Factory that runs ANY pipeline script as a separate, isolated process.
    This prevents ML memory leaks from crashing the main Flask server.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, f"{pipeline_name}.py")

    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Pipeline {pipeline_name} does not exist.")

    command = [
        "python",
        script_path,
        "--input_video",
        input_path,
        "--output_video",
        output_path,
    ]

    process = subprocess.run(command, capture_output=True, text=True)

    if process.returncode != 0:
        raise RuntimeError(f"Pipeline '{pipeline_name}' crashed:\n{process.stderr}")

    for line in process.stdout.split("\n"):
        if line.startswith("RESULT_JSON:"):
            result_data = json.loads(line.replace("RESULT_JSON:", "").strip())
            result_data["output"] = output_path
            return result_data

    return {
        "output": output_path,
        "status": "success",
        "message": "No specific stats returned by pipeline.",
    }
