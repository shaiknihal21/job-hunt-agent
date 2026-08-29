"use client";

import { useEffect, useState } from "react";
import { api, WeeklyReport, Application } from "@/lib/api";

export default function DashboardPage() {
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [pending, setPending] = useState(0);
  const [recent, setRecent] = useState<Application[]>([]);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const [r, queue, apps] = await Promise.all([
        api.getWeeklyReport(),
        api.getPendingApprovals(),
        api.getApplications(),
      ]);
      setReport(r);
      setPending(queue.length);
      setRecent(apps.slice(0, 5));
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleScan() {
    setScanning(true);
    setError("");
    try {
      await api.discoverJobs();
      await loadData();
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  }

  return (
    <div>
      <div className="hero">
        <h1>Job Hunt Agent</h1>
        <p>AI · Software · Data Engineer roles at product MNCs · India on-site or worldwide remote/WFH</p>
      </div>

      {error && <div className="card" style={{ borderColor: "#f4212e" }}>{error}</div>}

      <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
        {scanning ? "Scanning..." : "Scan for Jobs Now"}
      </button>

      {report && (
        <div className="grid" style={{ marginTop: 24 }}>
          <div className="stat">
            <div className="stat-value">{report.total_discovered}</div>
            <div className="stat-label">Discovered (7d)</div>
          </div>
          <div className="stat">
            <div className="stat-value">{report.total_applied}</div>
            <div className="stat-label">Applied (7d)</div>
          </div>
          <div className="stat">
            <div className="stat-value">{pending}</div>
            <div className="stat-label">Pending Approval</div>
          </div>
          <div className="stat">
            <div className="stat-value">{report.response_rate}%</div>
            <div className="stat-label">Response Rate</div>
          </div>
        </div>
      )}

      <h2 style={{ marginBottom: 16 }}>Recent Applications</h2>
      {recent.length === 0 ? (
        <div className="card">No applications yet. Scan for jobs and approve matches to get started.</div>
      ) : (
        recent.map((app) => (
          <div className="card" key={app.id}>
            <h3>{app.job?.title || "Unknown"} @ {app.job?.company || "Unknown"}</h3>
            <span className={`status status-${app.status === "applied" ? "applied" : "pending"}`}>
              {app.status}
            </span>
          </div>
        ))
      )}
    </div>
  );
}
