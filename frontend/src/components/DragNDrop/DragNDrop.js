import React, { useState } from 'react';
import './DragNDrop.css';

const DragNDrop = (props) => {
    const [file, setFile] = useState(null);
    const [isDraggingFile, setIsDraggingFile] = useState(false);

    const handleDragOver = (e) => {
        e.preventDefault();
        if (e.dataTransfer.items && e.dataTransfer.items[0].kind === 'file' && e.dataTransfer.items[0].type === 'application/pdf')
            setIsDraggingFile(true);

    };

    const handleDragLeave = () => {
        setIsDraggingFile(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        if (e.dataTransfer.items[0].type === 'application/pdf') {
            const droppedFile = e.dataTransfer.files[0];
        props.setDroppedFile(droppedFile);
        setFile(droppedFile);
        setIsDraggingFile(false);
        }
    };

    const openFileSelector = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf';
        input.onchange = (e) => {
            const selectedFile = e.target.files[0];
            props.setDroppedFile(selectedFile);
            setFile(selectedFile);
        };
        input.click();
    };

    return (
        <div className="dragndrop">
            <div
                className={`file-box ${isDraggingFile ? 'drag-hover' : ''}`}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onDragLeave={handleDragLeave}
                style={{ width: props.width, height: props.height }}
            >
                {isDraggingFile ? "Drop your resume here" : file ? file.name : "Drag and drop your resume or click to browse"}
                <button text="Upload" style={{ marginTop: '10px' }} onClick={() => {openFileSelector()}}>Browse</button>
            </div>
        </div>
    )
}

export default DragNDrop;