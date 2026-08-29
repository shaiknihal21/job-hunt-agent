"use client";

import { useEffect, useState } from "react";
import { api, Profile } from "../lib/api";

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [uploadMsg, setUploadMsg] = useState("");

  useEffect(() => {
    api.getProfile().then(setProfile);
  }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadMsg("Uploading...");
    try {
      await api.uploadResume(file);
      setUploadMsg(`Uploaded: ${file.name}`);
    } catch (err) {
      setUploadMsg(String(err));
    }
  }

  if (!profile) return <div className="card">Loading profile...</div>;

  return (
    <div>
      <h1 style={{ marginBottom: 24 }}>Profile</h1>

      <div className="card">
        <h3>{profile.name}</h3>
        <div className="meta">{profile.role} · {profile.location}</div>
        {profile.email && <div className="meta">{profile.email}</div>}
      </div>

      <div className="card">
        <h3>Target Roles</h3>
        <div style={{ marginTop: 8 }}>
          {profile.target_roles.map((r) => (
            <span className="tag" key={r}>{r}</span>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Skills</h3>
        <div style={{ marginTop: 8 }}>
          {profile.skills.map((s) => (
            <span className="tag" key={s}>{s}</span>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Master Resume</h3>
        <p className="meta">Upload PDF or DOCX to enable resume tailoring</p>
        <input type="file" accept=".pdf,.docx,.doc,.txt" onChange={handleUpload} />
        {uploadMsg && <p style={{ marginTop: 8 }}>{uploadMsg}</p>}
      </div>
    </div>
  );
}
