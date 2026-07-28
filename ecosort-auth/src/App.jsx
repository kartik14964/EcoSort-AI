import React, { useState } from "react";
import axios from "axios";
import "./App.css";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL;

function App() {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const endpoint = mode === "login" ? "/auth/login" : "/auth/register";

    try {
      const res = await axios.post(`${BACKEND_URL}${endpoint}`, {
        username,
        password,
      });
      const token = res.data.access_token;
      window.location.href = `${DASHBOARD_URL}/?token=${encodeURIComponent(token)}`;
    } catch (err) {
      setLoading(false);
      setError(
        err.response?.data?.detail ||
          (mode === "login" ? "Login failed." : "Registration failed.")
      );
    }
  };

  return (
    <div className="ec-page">
      <div className="ec-card">
        <h1 className="ec-title">EcoSort Secure Gateway</h1>
        <p className="ec-subtitle">Your private sustainability dashboard.</p>

        <div className="ec-tabs">
          <button
            className={mode === "login" ? "ec-tab ec-tab-active" : "ec-tab"}
            onClick={() => { setMode("login"); setError(""); }}
          >
            Log In
          </button>
          <button
            className={mode === "register" ? "ec-tab ec-tab-active" : "ec-tab"}
            onClick={() => { setMode("register"); setError(""); }}
          >
            Create Account
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <label className="ec-label">Username</label>
          <input
            className="ec-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="e.g. admin"
            required
          />

          <label className="ec-label">Password</label>
          <input
            className="ec-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
          />

          {error && <div className="ec-error">{error}</div>}

          <button type="submit" className="ec-submit-btn" disabled={loading}>
            {loading
              ? "Connecting..."
              : mode === "login"
              ? "Log In to Dashboard"
              : "Register New Account"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;