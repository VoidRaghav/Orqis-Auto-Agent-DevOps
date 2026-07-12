"use client";

import { API_URL } from "@/lib/env";
import { colors, fonts, mono } from "@/lib/tokens";

export default function LoginPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: colors.bg,
        padding: 24,
      }}
    >
      <div
        style={{
          maxWidth: 400,
          width: "100%",
          border: `1px solid ${colors.borderStrong}`,
          borderRadius: 16,
          padding: 40,
          background: colors.bg2,
          textAlign: "center",
        }}
      >
        <div style={{ fontFamily: fonts.anton, fontSize: 28, color: colors.white, marginBottom: 8 }}>
          ORQIS
        </div>
        <p style={{ ...mono, fontSize: 12, color: colors.dim, marginBottom: 32 }}>
          Sign in to your workspace
        </p>
        <a
          href={`${API_URL}/auth/github/login`}
          style={{
            display: "inline-block",
            padding: "12px 24px",
            borderRadius: 8,
            background: `${colors.github}18`,
            border: `1px solid ${colors.github}55`,
            color: colors.github,
            textDecoration: "none",
            fontWeight: 600,
            fontSize: 14,
          }}
        >
          Sign in with GitHub
        </a>
      </div>
    </div>
  );
}
