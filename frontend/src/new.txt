import React, { useState } from 'react';

function App() {
  const [resume, setResume] = useState('');
  const [jd, setJd] = useState('');
  const [result, setResult] = useState('');

  const handleEvaluate = async () => {
    const res = await fetch('http://localhost:5000/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume, job_description: jd })
    });
    const data = await res.json();
    setResult(data.result);
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h2>AI Resume Evaluator</h2>  
      <textarea
        placeholder="Paste your resume here"
        rows={10}
        cols={60}
        value={resume}
        onChange={(e) => setResume(e.target.value)}
      />
      <br />
      <textarea
        placeholder="Paste job description here"
        rows={10}
        cols={60}
        value={jd}
        onChange={(e) => setJd(e.target.value)}
      />
      <br />
      <button onClick={handleEvaluate}>Evaluate</button>
      <pre>{result}</pre>
    </div>
  );
}

export default App;
