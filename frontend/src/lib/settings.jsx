import { createContext, useContext, useState, useEffect } from 'react';

const SettingsContext = createContext();

const DEFAULT_SETTINGS = {
    // Board appearance
    pieceSet: 'classic',
    boardTheme: 'green',
    showCoordinates: true,
    highlightLastMove: true,

    // Animations
    animationsEnabled: true,
    animationSpeed: 200,

    // Sound
    soundEnabled: true,
    soundVolume: 0.5,

    // Tutorial
    tutorialCompleted: false,
};

export function SettingsProvider({ children }) {
    const [settings, setSettingsState] = useState(() => {
        const saved = localStorage.getItem('chessica_settings');
        return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS;
    });

    useEffect(() => {
        localStorage.setItem('chessica_settings', JSON.stringify(settings));
    }, [settings]);

    const updateSettings = (newSettings) => {
        setSettingsState(prev => ({ ...prev, ...newSettings }));
    };

    const resetSettings = () => {
        setSettingsState(DEFAULT_SETTINGS);
    };

    return (
        <SettingsContext.Provider value={{ settings, updateSettings, resetSettings }}>
            {children}
        </SettingsContext.Provider>
    );
}

export function useSettings() {
    const context = useContext(SettingsContext);
    if (!context) {
        throw new Error('useSettings must be used within SettingsProvider');
    }
    return context;
}

// Board theme configurations
export const BOARD_THEMES = {
    green: {
        name: 'Classic Green',
        light: '#edeed1',
        dark: '#779952',
    },
    brown: {
        name: 'Wooden Brown',
        light: '#f0d9b5',
        dark: '#b58863',
    },
    blue: {
        name: 'Ocean Blue',
        light: '#dee3e6',
        dark: '#8ca2ad',
    },
    gray: {
        name: 'Modern Gray',
        light: '#e8e8e8',
        dark: '#6b7280',
    },
    purple: {
        name: 'Royal Purple',
        light: '#e9d5ff',
        dark: '#9333ea',
    },
};

// Piece set configurations (for future expansion)
export const PIECE_SETS = {
    classic: { name: 'Classic' },
    modern: { name: 'Modern' },
    neo: { name: 'Neo' },
};
