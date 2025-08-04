from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

@app.route('/evaluate', methods=['POST'])
def evaluate():
    data = request.get_json()
    resume = data.get("resume", "")
    jd = data.get("job_description", "")

    prompt = f"""
You are a resume evaluator. Score the following resume against the job description.
Return a score out of 100 and 3 specific improvement suggestions.

Resume:
{resume}

Job Description:
{jd}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "tinyllama",
                "prompt": prompt,
                "stream": False
            }
        )
        response.raise_for_status()
        result = response.json()["response"]
        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
