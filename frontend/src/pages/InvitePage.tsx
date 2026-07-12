"use client";

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { API_URL } from "@/lib/env";

interface InvitePreview {
  workspace_name: string;
  workspace_id: string;
  role: string;
  created_by_login?: string;
}

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/invites/${token}/preview`)
      .then(async (r) => {
        if (!r.ok) throw new Error("Invite not found or expired");
        return r.json();
      })
      .then(setPreview)
      .catch((e) => setError(e.message));
  }, [token]);

  const joinUrl = token
    ? `${API_URL}/auth/github/login?invite=${encodeURIComponent(token)}`
    : "#";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#0a0c10",
        color: "#e8eaed",
        fontFamily: "system-ui, sans-serif",
        padding: 24,
      }}
    >
      <div
        style={{
          maxWidth: 420,
          width: "100%",
          padding: 32,
          border: "1px solid #2a2f3a",
          borderRadius: 12,
          background: "#12151c",
        }}
      >
        <h1 style={{ margin: "0 0 8px", fontSize: 22 }}>Join workspace</h1>
        {error && <p style={{ color: "#f87171" }}>{error}</p>}
        {preview && (
          <>
            <p style={{ color: "#9aa0a6", marginBottom: 24 }}>
              You&apos;ve been invited to <strong>{preview.workspace_name}</strong>
              {preview.created_by_login ? ` by ${preview.created_by_login}` : ""}.
            </p>
            <a
              href={joinUrl}
              style={{
                display: "block",
                textAlign: "center",
                padding: "12px 16px",
                background: "#238636",
                color: "#fff",
                borderRadius: 8,
                textDecoration: "none",
                fontWeight: 600,
              }}
            >
              Sign in with GitHub to join
            </a>
          </>
        )}
        {!error && !preview && <p style={{ color: "#9aa0a6" }}>Loading invite…</p>}
      </div>
    </div>
  );
}
