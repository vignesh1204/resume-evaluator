import React from 'react';
import {useNavigate} from 'react-router-dom';

import './HeroSection.css';
import CustomButton from '../../Button/CustomButton';

const HeroSection = () => {
    const navigate = useNavigate();

    const onClickTryBtn = () => {
        navigate('/app')
    }

    return (
        <div className='hero'>
            <h1 className='heading'>
                AI-Powered Resume Scoring Tool
            </h1>
            <h2 className="sub-heading">
                Quickly evaluate your resume against any job description and get actionable feedback — powered by smart AI.
            </h2>
            <CustomButton text="Try it now" onClick={onClickTryBtn} className="try-button"></CustomButton>
        </div>
    )
}

export default HeroSection;