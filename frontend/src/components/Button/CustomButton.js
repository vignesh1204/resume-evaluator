import React from 'react';
import './CustomButton.css';

const CustomButton = ({ text, onClick, disabled, type = 'button' }) => {
    return (
        <button
            className='custom-button'
            disabled={disabled}
            onClick={onClick}
            type={type}
            style={{
                opacity: disabled ? 0.5 : 1,
                cursor: disabled ? "not-allowed" : "pointer",
            }}>
            {text}
        </button>
    )
}

export default CustomButton;