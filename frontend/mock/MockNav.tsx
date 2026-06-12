import type { CSSProperties } from "react";

const bar: CSSProperties = {
  background: "#FBFAF6",
  borderBottom: "1px solid #D9D2C3",
  fontFamily: '"Inter", "Noto Sans JP", system-ui, sans-serif',
};

const inner: CSSProperties = {
  maxWidth: "1152px",
  margin: "0 auto",
  padding: "10px 120px 10px 22px",
  display: "flex",
  alignItems: "center",
  gap: "18px",
  flexWrap: "wrap",
};

const brand: CSSProperties = {
  fontWeight: 700,
  fontSize: "15px",
  color: "#1C1A17",
  textDecoration: "none",
};

const link: CSSProperties = {
  color: "#4A463F",
  textDecoration: "none",
  fontSize: "13px",
};

const current: CSSProperties = {
  ...link,
  color: "#1C7A45",
  fontWeight: 600,
};

export function MockNav() {
  return (
    <nav style={bar}>
      <div style={inner}>
        <a style={brand} href="../">
          Tanomude
        </a>
        <a style={current} href="./">
          インタラクティブモック
        </a>
        <a style={link} href="../status/">
          実装状況
        </a>
        <a style={link} href="../operations/">
          設計と技術選定
        </a>
      </div>
    </nav>
  );
}
