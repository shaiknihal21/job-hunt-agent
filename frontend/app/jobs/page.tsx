"use client";

import { useEffect, useState } from "react";
import { api, Job } from "../../lib/api";

function ScoreBadge({ score }: { score: number }) {
  const cls = score >= 80 ? "score-high" : "score-mid";
  return <span className={`score ${cls}`}>{score.toFixed(0)}%</span>;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [minScore, setMinScore] = useState(70);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadJobs();
  }, [minScore]);

  async function loadJobs() {
    setLoading(true);
    try {
      const data = await api.getJobs(minScore);
      setJobs(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>Job Feed</h1>
      <div style={{ marginBottom: 16 }}>
        <label>
          Min score:{" "}
          <input
            type="range"
            min={0}
            max={100}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
          />
          {minScore}%
        </label>
      </div>

      {loading ? (
        <div className="card">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="card">No jobs found. Run a scan from the dashboard.</div>
      ) : (
        jobs.map((job) => (
          <div className="card" key={job.id}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
              <div>
                <h3>{job.title}</h3>
                <div className="meta">
                  {job.company} · {job.location || "Unknown"} · {job.source}
                  {job.remote && " · Remote"}
                </div>
              </div>
              {job.score && <ScoreBadge score={job.score.score} />}
            </div>
            {job.salary_text && <div className="meta">{job.salary_text}</div>}
            {job.score && (
              <ul className="reasons">
                {job.score.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
            <a href={job.url} target="_blank" rel="noopener noreferrer">
              View job →
            </a>
          </div>
        ))
      )}
    </div>
  );
}
