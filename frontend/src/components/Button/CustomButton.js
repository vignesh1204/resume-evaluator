import React from 'react';
import './CustomButton.css';

const CustomButton = ({text, onClick, type='button'}) => {
    return (
        <button className='custom-button' onClick={onClick} type={type}>
            {text}
        </button>
    )
}

export default CustomButton;