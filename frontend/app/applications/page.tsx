"use client";

import { useEffect, useState } from "react";
import { api, Application, WeeklyReport } from "../../lib/api";

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [submitting, setSubmitting] = useState<number | null>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    const [applications, weekly] = await Promise.all([
      api.getApplications(),
      api.getWeeklyReport(),
    ]);
    setApps(applications);
    setReport(weekly);
  }

  async function handleSubmit(appId: number) {
    setSubmitting(appId);
    try {
      await api.submitApplication(appId);
      await load();
    } finally {
      setSubmitting(null);
    }
  }

  function statusClass(status: string) {
    if (status === "applied") return "status-applied";
    if (status === "interview") return "status-interview";
    if (status === "rejected") return "status-rejected";
    return "status-pending";
  }

  return (
    <div>
      <h1 style={{ marginBottom: 24 }}>Application Tracker</h1>

      {report && (
        <div className="grid">
          <div className="stat">
            <div className="stat-value">{report.total_applied}</div>
            <div className="stat-label">Applied</div>
          </div>
          <div className="stat">
            <div className="stat-value">{report.total_interviews}</div>
            <div className="stat-label">Interviews</div>
          </div>
          <div className="stat">
            <div className="stat-value">{report.total_rejected}</div>
            <div className="stat-label">Rejected</div>
          </div>
          <div className="stat">
            <div className="stat-value">{report.response_rate}%</div>
            <div className="stat-label">Response Rate</div>
          </div>
        </div>
      )}

      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th>Role</th>
            <th>Status</th>
            <th>Score</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((app) => (
            <tr key={app.id}>
              <td>{app.job?.company || "—"}</td>
              <td>{app.job?.title || "—"}</td>
              <td>
                <span className={`status ${statusClass(app.status)}`}>{app.status}</span>
              </td>
              <td>{app.job?.score?.score.toFixed(0) ?? "—"}%</td>
              <td>
                {app.status === "pending_submit" && (
                  <button
                    className="btn btn-primary"
                    onClick={() => handleSubmit(app.id)}
                    disabled={submitting === app.id}
                  >
                    Submit Application
                  </button>
                )}
                {app.apply_url && (
                  <a href={app.apply_url} target="_blank" rel="noopener noreferrer">
                    View
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {apps.length === 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          No applications yet. Approve jobs from the approval queue to start applying.
        </div>
      )}
    </div>
  );
}
