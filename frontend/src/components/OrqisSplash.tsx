"use client";

type Props = {
  visible: boolean;
  fading: boolean;
};

/** Text-only overlay — robot renders once in FlowZone rail behind this */
export default function OrqisSplash({ visible, fading }: Props) {
  if (!visible) return null;

  return (
    <div
      className={`orqis-splash${fading ? " orqis-splash--out" : ""}`}
      aria-hidden={fading}
    >
      <h1 className="orqis-splash-word">ORQIS</h1>
    </div>
  );
}
