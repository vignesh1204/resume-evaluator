import React, {useState} from 'react';
import CustomButton from '../Button/CustomButton';

const MainPage = () => {
    const [resumeData, setResumeData] = useState('');
    const [jobDesc, setJobDesc] = useState('');

    const onClickEvalBtn = () => {
        alert ("Evaluating..")
    }

    return (
        <div className='body'>
            <input
                type="text"
                placeholder="Enter your resume info"
                value={resumeData}
                onChange={(e) => setResumeData(e.target.value)}
            />
            <input
                type="text"
                placeholder="Enter the job description"
                value={jobDesc}
                onChange={(e) => setJobDesc(e.target.value)}
            />
            <CustomButton text="Evaluate" onClick={onClickEvalBtn}></CustomButton>
        </div>
    )
}

export default MainPage;