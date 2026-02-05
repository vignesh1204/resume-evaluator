import React, { useState } from 'react';
import pdfToText from 'react-pdftotext'

import CustomButton from '../Button/CustomButton';
import DragNDrop from '../DragNDrop/DragNDrop';

import './MainPage.css';
import { style } from 'd3';

const MainPage = () => {
    const [uploadedFile, setUploadedFile] = useState(null);
    const [jobDesc, setJobDesc] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const onClickEvalBtn = async () => {
        console.log("Uploaded file:", uploadedFile);
        setIsLoading(true);
        setError(null);
        setResult(null);
        
        try {
            
            const resume = await pdfToText(uploadedFile);
            console.log("Extracted resume text:", resume.substring(0, 200)); 
            
            
            const response = await fetch('http://localhost:5000/evaluate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    resume: resume, 
                    job_description: jobDesc 
                })
            });

            console.log("Response status:", response.status);
            
            if (!response.ok) {
                
                const errorText = await response.text();
                console.error("Server error response:", errorText);
                throw new Error(`Server error (${response.status}): ${errorText}`);
            }

            const data = await response.json();
            console.log("Success! Received data:", data);
            
            if (data.result) {
                setResult(data.result);
                if (data.warning) {
                    console.warn("Warning:", data.warning);
                }
            } else {
                throw new Error("No result data received from server");
            }
            
        } catch (error) {
            console.error("Error during evaluation:", error);
            setError(error.message);
        } finally {
            setIsLoading(false);
        }
    }

    const renderResult = () => {
        if (!result) return null;

        return (
            <div className="result-container" style={{
                marginTop: '20px',
                border: '1px solid #ccc',
                borderRadius: '8px',
                backgroundColor: '#f9f9f9',
            }}>
                <h3>Evaluation Result</h3>
                <div><strong>Score:</strong> {result.Score}</div>
                
                <div style={{ marginTop: '15px' }}>
                    <strong>Strengths:</strong>
                    <ul>
                        {result.Strengths?.map((strength, index) => (
                            <li key={index}>{strength}</li>
                        ))}
                    </ul>
                </div>
                
                <div style={{ marginTop: '15px' }}>
                    <strong>Weaknesses:</strong>
                    <ul>
                        {result.Weaknesses?.map((weakness, index) => (
                            <li key={index}>{weakness}</li>
                        ))}
                    </ul>
                </div>
                
                <div style={{ marginTop: '15px' }}>
                    <strong>Actionable Improvements:</strong>
                    <ul>
                        {result.Actionable_Improvements?.map((improvement, index) => (
                            <li key={index}>{improvement}</li>
                        ))}
                    </ul>
                </div>

                {result.raw_analysis && (
                    <details style={{ marginTop: '15px', color: 'black' }}>
                        <summary>Raw Analysis (Click to expand)</summary>
                        <pre style={{ whiteSpace: 'pre-wrap', fontSize: '12px', color: 'black'}}>
                            {result.raw_analysis}
                        </pre>
                    </details>
                )}
            </div>
        );
    };

    const renderError = () => {
        if (!error) return null;

        return (
            <div className="error-container" style={{
                marginTop: '20px',
                padding: '20px',
                border: '1px solid #ff6b6b',
                borderRadius: '8px',
                backgroundColor: '#ffe0e0',
                color: '#d63031'
            }}>
                <h3>Error</h3>
                <p>{error}</p>
                <details>
                    <summary>Troubleshooting Tips</summary>
                    <ul>
                        <li>Make sure your Flask server is running on port 5000</li>
                        <li>Check the terminal where Flask is running for error messages</li>
                        <li>Try uploading a different PDF file</li>
                        <li>Make sure the job description is not empty</li>
                    </ul>
                </details>
            </div>
        );
    };

    return (
        <div className='body'>
            <p className='heading'>Resume Evaluator</p>
            <div className='section-container'>
                <DragNDrop width='650px' height='410px' setDroppedFile={setUploadedFile} />
                <textarea
                    type="text"
                    placeholder="Enter the job description.."
                    className='jd-input'
                    value={jobDesc}
                    onChange={(e) => setJobDesc(e.target.value)}
                />
            </div>
            
            <CustomButton 
                text={isLoading ? "Evaluating..." : "Evaluate"} 
                disabled={!uploadedFile || !jobDesc.trim() || isLoading} 
                onClick={onClickEvalBtn}
            />
            
            {renderError()}
            {renderResult()}
        </div>
    )
}

export default MainPage;