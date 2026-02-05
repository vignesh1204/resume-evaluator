from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

client = OpenAI()

@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json() or {}
    resume = data.get("resume", "")
    jd = data.get("job_description", "")

    prompt = f"""
You are an ATS-style resume evaluator.
Score this resume against the job description.

Return ONLY valid JSON in this exact format:
{{
  "Score": "0 to 100",
  "Strengths": ["point 1", "point 2", "point 3"],
  "Weaknesses": ["point 1", "point 2", "point 3"],
  "Actionable_Improvements": [
    "Specific, realistic, ATS-focused recommendation 1",
    "Specific recommendation 2",
    "Specific recommendation 3"
  ]
}}

Resume:
{resume[:3000]}

Job Description:
{jd}
""".strip()

    try:
        resp = client.responses.create(
            model="gpt-5.2",
            input=prompt,
            text={"format": {"type": "json_object"}},
        )

        raw = resp.output_text
        evaluation_result = json.loads(raw)
        return jsonify({"result": evaluation_result})

    except json.JSONDecodeError:
        return jsonify({"error": "Model returned invalid JSON", "raw_response": raw}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    
