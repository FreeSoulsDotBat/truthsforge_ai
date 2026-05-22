// Shared atoms for the Truth's Forge AI design system

function StatusDot({ color = "var(--ember)", size = 7, pulse = false }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: size,
        height: size,
        borderRadius: "999px",
        background: color,
        boxShadow: pulse ? `0 0 0 4px ${color.replace("var(--ember)", "var(--ember-glow)")}` : "none",
        flexShrink: 0,
      }}
    />
  );
}

function Pulse({ color = "var(--ember)", size = 6 }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: size, height: size, flexShrink: 0 }}>
      <span style={{ position: "absolute", inset: 0, borderRadius: "999px", background: color, animation: "tfPulse 2s infinite ease-in-out" }} />
      <span style={{ position: "relative", width: size, height: size, borderRadius: "999px", background: color }} />
    </span>
  );
}

function Mono({ children, size = 11, color = "var(--muted)", style = {}, ...props }) {
  return (
    <span
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: size,
        letterSpacing: "0.04em",
        color,
        ...style,
      }}
      {...props}
    >
      {children}
    </span>
  );
}

function Chip({ label, value, dot = false, dotColor = "var(--ember)", style = {} }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        height: 28,
        padding: "0 10px",
        borderRadius: 999,
        background: "var(--bg-chip)",
        color: "var(--text-soft)",
        fontSize: 12,
        ...style,
      }}
    >
      {dot && <StatusDot color={dotColor} />}
      {label && (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          {label}
        </span>
      )}
      <span style={{ color: "var(--text)" }}>{value}</span>
    </span>
  );
}

function Tag({ children, tone = "neutral", style = {} }) {
  const tones = {
    neutral: { bg: "var(--bg-chip)", color: "var(--muted)", border: "transparent" },
    ember: { bg: "color-mix(in srgb, var(--ember) 12%, transparent)", color: "var(--ember)", border: "color-mix(in srgb, var(--ember) 25%, transparent)" },
    amethyst: { bg: "color-mix(in srgb, var(--amethyst) 14%, transparent)", color: "var(--amethyst)", border: "color-mix(in srgb, var(--amethyst) 28%, transparent)" },
    azure: { bg: "color-mix(in srgb, var(--azure) 12%, transparent)", color: "var(--azure)", border: "color-mix(in srgb, var(--azure) 25%, transparent)" },
    ok: { bg: "color-mix(in srgb, var(--ok) 12%, transparent)", color: "var(--ok)", border: "transparent" },
    warn: { bg: "color-mix(in srgb, var(--warn) 12%, transparent)", color: "var(--warn)", border: "transparent" },
    err: { bg: "color-mix(in srgb, var(--err) 12%, transparent)", color: "var(--err)", border: "color-mix(in srgb, var(--err) 28%, transparent)" },
  };
  const t = tones[tone] || tones.neutral;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 8px",
        borderRadius: 6,
        background: t.bg,
        color: t.color,
        border: `1px solid ${t.border}`,
        fontFamily: "var(--font-mono)",
        fontSize: 10.5,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        ...style,
      }}
    >
      {children}
    </span>
  );
}

function KBD({ children }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: 18,
        height: 18,
        padding: "0 5px",
        borderRadius: 4,
        background: "var(--bg-chip)",
        color: "var(--muted)",
        fontFamily: "var(--font-mono)",
        fontSize: 10,
      }}
    >
      {children}
    </span>
  );
}

function Avatar({ kind = "user", size = 26, theme }) {
  if (kind === "judite") {
    return (
      <span
        style={{
          width: size,
          height: size,
          borderRadius: 999,
          background: "radial-gradient(circle at 30% 30%, var(--ember), color-mix(in srgb, var(--ember) 40%, var(--bg-ink)))",
          boxShadow: "0 0 0 1px color-mix(in srgb, var(--ember) 35%, transparent), 0 8px 22px -10px var(--ember-glow)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--ember-ink)",
          flexShrink: 0,
          position: "relative",
        }}
      >
        <span style={{ fontFamily: "var(--font-display)", fontSize: size * 0.5, fontWeight: 400, letterSpacing: "0.02em" }}>J</span>
      </span>
    );
  }
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: 999,
        background: "var(--bg-chip)",
        border: "1px solid var(--line-soft)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--muted)",
        fontSize: size * 0.4,
        flexShrink: 0,
      }}
    >
      <Icon name="user" size={size * 0.5} />
    </span>
  );
}

function NavItem({ icon, label, active = false, count, badge }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        height: 34,
        padding: "0 10px",
        borderRadius: 8,
        background: active ? "var(--bg-card)" : "transparent",
        color: active ? "var(--text)" : "var(--muted)",
        fontSize: 13,
        position: "relative",
        cursor: "default",
      }}
    >
      {active && (
        <span
          style={{
            position: "absolute",
            left: -10,
            top: 8,
            bottom: 8,
            width: 2,
            borderRadius: 2,
            background: "var(--ember)",
          }}
        />
      )}
      <span style={{ color: active ? "var(--ember)" : "var(--muted)" }}>{icon}</span>
      <span style={{ flex: 1, fontWeight: active ? 500 : 400 }}>{label}</span>
      {badge && (
        <Mono size={10} color={active ? "var(--ember)" : "var(--faint)"}>
          {badge}
        </Mono>
      )}
      {count !== undefined && (
        <Mono size={10} color={active ? "var(--text-soft)" : "var(--faint)"}>
          {count}
        </Mono>
      )}
    </div>
  );
}

function SectionLabel({ children, action }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 12px 6px",
        color: "var(--muted)",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--faint)",
        }}
      >
        {children}
      </span>
      {action}
    </div>
  );
}

function Divider({ vertical = false, style = {} }) {
  return (
    <span
      style={{
        display: "block",
        background: "var(--line-soft)",
        ...(vertical ? { width: 1, alignSelf: "stretch" } : { height: 1, width: "100%" }),
        ...style,
      }}
    />
  );
}

Object.assign(window, { StatusDot, Pulse, Mono, Chip, Tag, KBD, Avatar, NavItem, SectionLabel, Divider });
