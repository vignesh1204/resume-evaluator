import React, { useState } from 'react';
import pdfToText from 'react-pdftotext'

import CustomButton from '../Button/CustomButton';
import DragNDrop from '../DragNDrop/DragNDrop';

import './MainPage.css';

const MainPage = () => {
    const [uploadedFile, setUploadedFile] = useState(null);
    const [jobDesc, setJobDesc] = useState('');

    const onClickEvalBtn = () => {
        pdfToText(uploadedFile)
            .then((data) => {
                console.log(data);
            })
            .catch((error) => {
                console.error(error);
            });
    }

    return (
        <div className='body'>
            <p className='heading'> Resume Evaluator</p>
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
            <CustomButton text="Evaluate" onClick={onClickEvalBtn}></CustomButton>
        </div>
    )
}

export default MainPage;