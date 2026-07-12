import { colors, mono } from "@/lib/tokens";

export const settingsColors = {
  green: colors.green,
  amber: colors.amber,
  red: colors.red,
  blue: colors.github,
  github: colors.github,
  dim: colors.dim,
  muted: colors.muted,
  bg: colors.bg,
  bg2: colors.bg2,
  border: colors.border,
};

export function Card({
  title,
  children,
  accent,
  wide,
}: {
  title: string;
  children: React.ReactNode;
  accent?: string;
  wide?: boolean;
}) {
  return (
    <section className={`settings-card corner-brackets${wide ? " settings-card-wide" : ""}`} style={{ borderLeftColor: accent }}>
      <div className="settings-card-head" style={{ borderLeftColor: accent }}>
        <span style={{ ...mono }}>{title}</span>
      </div>
      <div className="settings-card-body">{children}</div>
    </section>
  );
}

export function Row({ label, value, tone, mono: isMono }: { label: string; value: string; tone?: string; mono?: boolean }) {
  return (
    <div className="settings-row">
      <span className="settings-row-label">{label}</span>
      <span className="settings-row-value" style={{ color: tone, ...(isMono ? mono : {}) }}>
        {value}
      </span>
    </div>
  );
}

export function Hint({ children, tone }: { children: React.ReactNode; tone?: "warn" }) {
  return <p className={`settings-hint${tone === "warn" ? " settings-hint-warn" : ""}`}>{children}</p>;
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="settings-field">
      <span className="settings-field-label">{label}</span>
      {children}
    </label>
  );
}

export function RepoSelect({
  repos,
  value,
  placeholder,
  onChange,
}: {
  repos: string[];
  value: string;
  placeholder: string;
  onChange: (repo: string) => void;
}) {
  return (
    <select value={value || ""} onChange={(e) => onChange(e.target.value)} className="settings-select">
      <option value="">{placeholder}</option>
      {repos.map((r) => (
        <option key={r} value={r}>
          {r}
        </option>
      ))}
    </select>
  );
}

export function Toggle({
  label,
  checked,
  onChange,
  danger,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  danger?: boolean;
}) {
  const accent = danger ? settingsColors.red : settingsColors.green;
  return (
    <label className="settings-toggle">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className="settings-switch"
        style={{
          borderColor: checked ? accent : settingsColors.border,
          background: checked ? `${accent}30` : "transparent",
        }}
      >
        <span className="settings-switch-knob" style={{ left: checked ? 18 : 2, background: checked ? accent : settingsColors.dim }} />
      </button>
      <span className="settings-toggle-label">{label}</span>
    </label>
  );
}
