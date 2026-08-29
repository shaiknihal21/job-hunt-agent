"use client";

import { useEffect, useState } from "react";
import { api, Job } from "../../lib/api";

export default function ApprovalsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionJob, setActionJob] = useState<number | null>(null);
  const [result, setResult] = useState<string>("");

  useEffect(() => {
    loadQueue();
  }, []);

  async function loadQueue() {
    setLoading(true);
    try {
      const data = await api.getPendingApprovals();
      setJobs(data);
    } finally {
      setLoading(false);
    }
  }

  async function handleDecision(jobId: number, decision: "approve" | "skip") {
    setActionJob(jobId);
    setResult("");
    try {
      const res = await api.approveJob(jobId, decision);
      setResult(`Job ${jobId}: ${res.status}${res.summary ? ` — ${res.summary.slice(0, 100)}...` : ""}`);
      await loadQueue();
    } catch (e) {
      setResult(String(e));
    } finally {
      setActionJob(null);
    }
  }

  return (
    <div>
      <h1 style={{ marginBottom: 8 }}>Approval Queue</h1>
      <p className="meta" style={{ marginBottom: 24 }}>
        Review AI / Software / Data Engineer matches at product MNCs (remote/WFH for abroad roles)
      </p>

      {result && <div className="card">{result}</div>}

      {loading ? (
        <div className="card">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="card">No jobs pending approval. Run a scan to discover new roles.</div>
      ) : (
        jobs.map((job) => (
          <div className="card" key={job.id}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
              <div>
                <h3>{job.title}</h3>
                <div className="meta">
                  {job.company} · {job.location} · Score: {job.score?.score.toFixed(0)}%
                </div>
              </div>
            </div>

            {job.score && (
              <>
                <ul className="reasons">
                  {job.score.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
                {job.score.red_flags.length > 0 && (
                  <ul className="reasons red-flags">
                    {job.score.red_flags.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                )}
              </>
            )}

            {job.description && (
              <p style={{ fontSize: "0.875rem", color: "#71767b", margin: "12px 0" }}>
                {job.description.slice(0, 300)}...
              </p>
            )}

            <div style={{ marginTop: 16 }}>
              <button
                className="btn btn-success"
                onClick={() => handleDecision(job.id, "approve")}
                disabled={actionJob === job.id}
              >
                Approve & Tailor Resume
              </button>
              <button
                className="btn btn-danger"
                onClick={() => handleDecision(job.id, "skip")}
                disabled={actionJob === job.id}
              >
                Skip
              </button>
              <a href={job.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary">
                View Job
              </a>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
