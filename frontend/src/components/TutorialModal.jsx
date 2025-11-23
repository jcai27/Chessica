import { useState, useEffect } from 'react';
import { useSettings } from '../lib/settings';
import './TutorialModal.css';

const TUTORIAL_STEPS = [
    {
        title: 'Welcome to Chessica! 👋',
        content: 'Learn how to master chess by exploiting your opponent\'s weaknesses. Let me show you around.',
        icon: '♟︎',
    },
    {
        title: 'Exploit Mode 🎯',
        content: 'Our AI doesn\'t just play the best moves—it adapts to exploit your opponent\'s specific patterns and mistakes. Watch as it learns their tendencies and capitalizes on them.',
        icon: '🧠',
    },
    {
        title: 'Real-Time Coaching 💡',
        content: 'Get live position analysis and strategic insights as you play. The coach explains key ideas, candidate moves, and tactical opportunities in plain language.',
        icon: '📊',
    },
    {
        title: 'Deep Analytics 📈',
        content: 'After each game, review detailed analysis showing how the AI exploited weaknesses, what patterns it detected, and how you can improve.',
        icon: '🔍',
    },
    {
        title: 'Ready to Play? 🚀',
        content: 'Start a game against the AI and watch exploit-aware chess in action. Good luck!',
        icon: '⚡',
    },
];

function TutorialModal({ onComplete }) {
    const { settings, updateSettings } = useSettings();
    const [currentStep, setCurrentStep] = useState(0);
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        // Show tutorial if not completed
        if (!settings.tutorialCompleted) {
            setTimeout(() => setIsVisible(true), 500);
        }
    }, [settings.tutorialCompleted]);

    const handleNext = () => {
        if (currentStep < TUTORIAL_STEPS.length - 1) {
            setCurrentStep(currentStep + 1);
        } else {
            handleComplete();
        }
    };

    const handleSkip = () => {
        handleComplete();
    };

    const handleComplete = () => {
        updateSettings({ tutorialCompleted: true });
        setIsVisible(false);
        if (onComplete) onComplete();
    };

    if (!isVisible) return null;

    const step = TUTORIAL_STEPS[currentStep];
    const isLastStep = currentStep === TUTORIAL_STEPS.length - 1;

    return (
        <div className="tutorial-overlay">
            <div className="tutorial-modal">
                <div className="tutorial-icon">{step.icon}</div>

                <h2 className="tutorial-title">{step.title}</h2>
                <p className="tutorial-content">{step.content}</p>

                <div className="tutorial-progress">
                    {TUTORIAL_STEPS.map((_, index) => (
                        <div
                            key={index}
                            className={`progress-dot ${index === currentStep ? 'active' : ''} ${index < currentStep ? 'completed' : ''
                                }`}
                        />
                    ))}
                </div>

                <div className="tutorial-actions">
                    {!isLastStep && (
                        <button type="button" className="tutorial-skip" onClick={handleSkip}>
                            Skip Tutorial
                        </button>
                    )}
                    <button type="button" className="tutorial-next" onClick={handleNext}>
                        {isLastStep ? 'Start Playing' : 'Next'}
                    </button>
                </div>

                <div className="tutorial-footer">
                    Step {currentStep + 1} of {TUTORIAL_STEPS.length}
                </div>
            </div>
        </div>
    );
}

export default TutorialModal;
