import type { CSSProperties } from "react";

const badge: CSSProperties = {
  position: "fixed",
  top: "12px",
  right: "12px",
  zIndex: 50,
  display: "inline-flex",
  alignItems: "center",
  gap: "0.5rem",
  borderRadius: "9999px",
  border: "1px solid #E7C9A0",
  background: "#FBEEDC",
  color: "#92400E",
  padding: "0.35rem 0.8rem",
  fontSize: "12px",
  fontWeight: 600,
  fontFamily: '"Inter", "Noto Sans JP", system-ui, sans-serif',
  boxShadow: "0 6px 16px -8px rgba(0,0,0,0.3)",
};

const dot: CSSProperties = {
  width: "8px",
  height: "8px",
  borderRadius: "9999px",
  background: "#D97706",
};

export function MockBadge() {
  return (
    <div style={badge}>
      <span style={dot} />
      モック
    </div>
  );
}
