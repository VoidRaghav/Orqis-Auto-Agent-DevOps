"use client";

import { C } from "../constants";
import { mono } from "../shared";

export default function DiffViewer({ diff }: { diff: string }) {
  return (
    <div style={{ padding: "8px 0" }}>
      {diff.split("\n").map((line, i) => {
        const isAdd = line.startsWith("+") && !line.startsWith("+++");
        const isRem = line.startsWith("-") && !line.startsWith("---");
        const isAt = line.startsWith("@@");
        return (
          <div
            key={i}
            style={{
              display: "flex",
              background: isAdd ? "rgba(0,255,136,0.07)" : isRem ? "rgba(255,51,51,0.07)" : "transparent",
              borderLeft: `3px solid ${isAdd ? C.green : isRem ? C.red : "transparent"}`,
            }}
          >
            <span
              style={{
                ...mono,
                fontSize: 11,
                color: isAdd ? C.green : isRem ? C.red : isAt ? C.blue : C.dim,
                padding: "2px 12px",
                userSelect: "none",
                minWidth: 16,
              }}
            >
              {isAdd ? "+" : isRem ? "−" : " "}
            </span>
            <span
              style={{
                ...mono,
                fontSize: 11,
                color: isAdd ? "rgba(0,255,136,0.9)" : isRem ? "rgba(255,51,51,0.8)" : isAt ? C.blue : "#555",
                padding: "2px 8px 2px 0",
                wordBreak: "break-all",
              }}
            >
              {line.slice(1) || line}
            </span>
          </div>
        );
      })}
    </div>
  );
}
