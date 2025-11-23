import { useState } from 'react';
import { useSettings, BOARD_THEMES, PIECE_SETS } from '../lib/settings';

function SettingsPage() {
    const { settings, updateSettings, resetSettings } = useSettings();
    const [message, setMessage] = useState('');

    const handleBoardThemeChange = (themeId) => {
        updateSettings({ boardTheme: themeId });
        setMessage('Board theme updated!');
        setTimeout(() => setMessage(''), 2000);
    };

    const handlePieceSetChange = (setId) => {
        updateSettings({ pieceSet: setId });
        setMessage('Piece set updated!');
        setTimeout(() => setMessage(''), 2000);
    };

    const handleAnimationSpeedChange = (speed) => {
        updateSettings({ animationSpeed: parseInt(speed) });
    };

    const handleVolumeChange = (volume) => {
        updateSettings({ soundVolume: parseFloat(volume) });
    };

    const handleResetSettings = () => {
        if (confirm('Reset all settings to defaults?')) {
            resetSettings();
            setMessage('Settings reset to defaults!');
            setTimeout(() => setMessage(''), 2000);
        }
    };

    const handleRestartTutorial = () => {
        updateSettings({ tutorialCompleted: false });
        setMessage('Tutorial will show on next page load!');
        setTimeout(() => setMessage(''), 3000);
    };

    return (
        <div className="app">
            <div className="page-grid">
                <div className="settings-main">
                    <header className="card hero hero-card">
                        <div className="hero-title">
                            <div className="badge">
                                <span>⚙️</span>
                            </div>
                            <div>
                                <h1>Settings</h1>
                                <p>Customize your Chessica experience</p>
                            </div>
                        </div>
                        <span className="pill">Preferences</span>
                    </header>

                    <section className="card">
                        <h2 className="section-title">
                            <span>Board Appearance</span>
                        </h2>

                        <div className="settings-group">
                            <label className="settings-label">
                                <span>Board Theme</span>
                                <span className="muted">Choose your preferred board colors</span>
                            </label>
                            <div className="theme-grid">
                                {Object.entries(BOARD_THEMES).map(([id, theme]) => (
                                    <button
                                        key={id}
                                        type="button"
                                        className={`theme-option ${settings.boardTheme === id ? 'active' : ''}`}
                                        onClick={() => handleBoardThemeChange(id)}
                                    >
                                        <div className="theme-preview">
                                            <div className="theme-square light" style={{ background: theme.light }} />
                                            <div className="theme-square dark" style={{ background: theme.dark }} />
                                        </div>
                                        <span>{theme.name}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="settings-group">
                            <label className="settings-label">
                                <span>Piece Set</span>
                                <span className="muted">Choose your preferred piece style</span>
                            </label>
                            <div className="piece-set-grid">
                                {Object.entries(PIECE_SETS).map(([id, set]) => (
                                    <button
                                        key={id}
                                        type="button"
                                        className={`piece-set-option ${settings.pieceSet === id ? 'active' : ''}`}
                                        onClick={() => handlePieceSetChange(id)}
                                    >
                                        {set.name}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="settings-group">
                            <label className="toggle-setting">
                                <div>
                                    <span>Show Board Notation</span>
                                    <span className="muted">Display file & rank labels</span>
                                </div>
                                <input
                                    type="checkbox"
                                    checked={settings.showCoordinates}
                                    onChange={(e) => updateSettings({ showCoordinates: e.target.checked })}
                                    className="toggle-input"
                                />
                            </label>
                        </div>

                        <div className="settings-group">
                            <label className="toggle-setting">
                                <div>
                                    <span>Highlight Last Move</span>
                                    <span className="muted">Show last move squares</span>
                                </div>
                                <input
                                    type="checkbox"
                                    checked={settings.highlightLastMove}
                                    onChange={(e) => updateSettings({ highlightLastMove: e.target.checked })}
                                    className="toggle-input"
                                />
                            </label>
                        </div>
                    </section>

                    <section className="card">
                        <h2 className="section-title">
                            <span>Animations</span>
                        </h2>

                        <div className="settings-group">
                            <label className="toggle-setting">
                                <div>
                                    <span>Enable Animations</span>
                                    <span className="muted">Smooth piece movements</span>
                                </div>
                                <input
                                    type="checkbox"
                                    checked={settings.animationsEnabled}
                                    onChange={(e) => updateSettings({ animationsEnabled: e.target.checked })}
                                    className="toggle-input"
                                />
                            </label>
                        </div>

                        <div className="settings-group">
                            <label className="slider-setting">
                                <div className="slider-header">
                                    <span>Animation Speed</span>
                                    <span className="slider-value">{settings.animationSpeed}ms</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="500"
                                    step="50"
                                    value={settings.animationSpeed}
                                    onChange={(e) => handleAnimationSpeedChange(e.target.value)}
                                    disabled={!settings.animationsEnabled}
                                    className="slider"
                                />
                                <div className="slider-labels">
                                    <span className="muted">Instant</span>
                                    <span className="muted">Slow</span>
                                </div>
                            </label>
                        </div>
                    </section>

                    <section className="card">
                        <h2 className="section-title">
                            <span>Sound</span>
                        </h2>

                        <div className="settings-group">
                            <label className="toggle-setting">
                                <div>
                                    <span>Enable Sound</span>
                                    <span className="muted">Play move and capture sounds</span>
                                </div>
                                <input
                                    type="checkbox"
                                    checked={settings.soundEnabled}
                                    onChange={(e) => updateSettings({ soundEnabled: e.target.checked })}
                                    className="toggle-input"
                                />
                            </label>
                        </div>

                        <div className="settings-group">
                            <label className="slider-setting">
                                <div className="slider-header">
                                    <span>Volume</span>
                                    <span className="slider-value">{Math.round(settings.soundVolume * 100)}%</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={settings.soundVolume}
                                    onChange={(e) => handleVolumeChange(e.target.value)}
                                    disabled={!settings.soundEnabled}
                                    className="slider"
                                />
                                <div className="slider-labels">
                                    <span className="muted">Quiet</span>
                                    <span className="muted">Loud</span>
                                </div>
                            </label>
                        </div>
                    </section>

                    <section className="card">
                        <h2 className="section-title">
                            <span>Tutorial & Help</span>
                        </h2>

                        <div className="settings-group">
                            <button
                                type="button"
                                className="settings-button secondary"
                                onClick={handleRestartTutorial}
                            >
                                <span>🎓</span>
                                <div>
                                    <span>Restart Tutorial</span>
                                    <span className="muted">Show the onboarding guide again</span>
                                </div>
                            </button>
                        </div>
                    </section>

                    <section className="card">
                        <h2 className="section-title">
                            <span>Advanced</span>
                        </h2>

                        <div className="settings-group">
                            <button
                                type="button"
                                className="settings-button danger"
                                onClick={handleResetSettings}
                            >
                                <span>⚠️</span>
                                <div>
                                    <span>Reset All Settings</span>
                                    <span className="muted">Restore default preferences</span>
                                </div>
                            </button>
                        </div>
                    </section>

                    {message && (
                        <div className="settings-message">
                            {message}
                        </div>
                    )}
                </div>

                <div className="settings-sidebar">
                    <section className="card">
                        <h3>Preview</h3>
                        <div className="board-preview-container">
                            <div
                                className="board-preview"
                                style={{
                                    background: `linear-gradient(45deg, ${BOARD_THEMES[settings.boardTheme].dark} 25%, transparent 25%, transparent 75%, ${BOARD_THEMES[settings.boardTheme].dark} 75%), linear-gradient(45deg, ${BOARD_THEMES[settings.boardTheme].dark} 25%, ${BOARD_THEMES[settings.boardTheme].light} 25%, ${BOARD_THEMES[settings.boardTheme].light} 75%, ${BOARD_THEMES[settings.boardTheme].dark} 75%)`,
                                    backgroundSize: '50px 50px',
                                    backgroundPosition: '0 0, 25px 25px',
                                }}
                            >
                                <div className="preview-piece">♔</div>
                            </div>
                        </div>
                        <p className="muted" style={{ fontSize: '0.85rem', marginTop: '0.75rem' }}>
                            Current board theme preview
                        </p>
                    </section>

                    <section className="card">
                        <h3>Quick Tips</h3>
                        <ul className="tips-list">
                            <li>
                                <span className="tip-icon">💡</span>
                                <span>Board themes are saved automatically</span>
                            </li>
                            <li>
                                <span className="tip-icon">🎨</span>
                                <span>Try different themes for better visibility</span>
                            </li>
                            <li>
                                <span className="tip-icon">⚡</span>
                                <span>Disable animations for faster gameplay</span>
                            </li>
                            <li>
                                <span className="tip-icon">🔊</span>
                                <span>Sound helps track opponent moves</span>
                            </li>
                        </ul>
                    </section>
                </div>
            </div>
        </div>
    );
}

export default SettingsPage;
