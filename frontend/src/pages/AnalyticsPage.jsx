import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatEval } from "../lib/format";

function AnalyticsPage() {
    const [userId, setUserId] = useState("user123"); // Hardcoded for demo
    const [stats, setStats] = useState(null);
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsData, profileData] = await Promise.all([
                    api.get(`/analytics/stats/${userId}`),
                    api.get(`/analytics/profile/${userId}`)
                ]);
                setStats(statsData);
                setProfile(profileData);
            } catch (err) {
                console.error("Failed to load analytics", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [userId]);

    if (loading) return <div className="app"><div className="page-grid">Loading...</div></div>;

    return (
        <div className="app">
            <div className="page-grid">
                <header className="card hero hero-card">
                    <div className="hero-title">
                        <div className="badge">
                            <span>📊</span>
                        </div>
                        <div>
                            <h1>Analytics Dashboard</h1>
                            <p>Performance metrics and opponent modeling insights.</p>
                        </div>
                    </div>
                </header>

                <div className="card">
                    <h2>Performance Stats</h2>
                    <div className="stats-grid">
                        <div className="stat-item">
                            <span className="stat-label">Games Played</span>
                            <span className="stat-value">{stats?.total_games || 0}</span>
                        </div>
                        <div className="stat-item">
                            <span className="stat-label">Win Rate</span>
                            <span className="stat-value">{Math.round((stats?.win_rate || 0) * 100)}%</span>
                        </div>
                        <div className="stat-item">
                            <span className="stat-label">Wins</span>
                            <span className="stat-value success">{stats?.wins || 0}</span>
                        </div>
                        <div className="stat-item">
                            <span className="stat-label">Losses</span>
                            <span className="stat-value danger">{stats?.losses || 0}</span>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <h2>Opponent Model Profile</h2>
                    <p className="muted">How the engine sees your playstyle.</p>

                    <div className="profile-section">
                        <h3>Style Vector</h3>
                        <div className="bar-chart">
                            <div className="bar-row">
                                <span className="bar-label">Tactical</span>
                                <div className="bar-track">
                                    <div
                                        className="bar-fill"
                                        style={{ width: `${(profile?.style?.tactical || 0.5) * 100}%` }}
                                    />
                                </div>
                                <span className="bar-value">{Math.round((profile?.style?.tactical || 0) * 100)}%</span>
                            </div>
                            <div className="bar-row">
                                <span className="bar-label">Risk Taking</span>
                                <div className="bar-track">
                                    <div
                                        className="bar-fill"
                                        style={{ width: `${(profile?.style?.risk || 0.5) * 100}%` }}
                                    />
                                </div>
                                <span className="bar-value">{Math.round((profile?.style?.risk || 0) * 100)}%</span>
                            </div>
                        </div>
                    </div>

                    <div className="profile-section">
                        <h3>Motif Risks</h3>
                        <div className="tag-cloud">
                            {Object.entries(profile?.motif_risks || {}).map(([motif, risk]) => (
                                <div key={motif} className="risk-tag" style={{ opacity: 0.5 + (risk * 0.5) }}>
                                    <span className="motif-name">{motif}</span>
                                    <span className="risk-value">{Math.round(risk * 100)}% Risk</span>
                                </div>
                            ))}
                            {Object.keys(profile?.motif_risks || {}).length === 0 && (
                                <span className="muted">No specific weaknesses detected yet.</span>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default AnalyticsPage;
