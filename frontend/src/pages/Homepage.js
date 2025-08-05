import React from 'react';

import './Homepage.css';
import HeroSection from '../components/Homepage/HeroSection';
import InfoSection from '../components/Homepage/InfoSection';
import ContactSection from '../components/Homepage/ContactSection';

const Homepage = () => {
    return (
        <div className="body">
            <HeroSection />
            {/* <InfoSection /> */}
            {/* <ContactSection /> */}
        </div>
    );
};

export default Homepage;