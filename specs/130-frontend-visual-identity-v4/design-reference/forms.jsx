// Form components — Field, NumberInput, Select, Toggle, Checkbox, Radio, Textarea

function FormField({ label, required, tip, children, hint, error }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
          {label}
        </Mono>
        {required && <span style={{ color: "var(--ember)", fontSize: 12 }}>*</span>}
        {tip && (
          <span style={{ width: 14, height: 14, borderRadius: 999, border: "1px solid var(--line)", display: "inline-flex", alignItems: "center", justifyContent: "center", color: "var(--muted)" }}>
            <Mono size={9} color="var(--muted)">?</Mono>
          </span>
        )}
      </div>
      {children}
      {hint && !error && <Mono size={10} color="var(--muted)">{hint}</Mono>}
      {error && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--err)" }}>
          <Icon name="shield" size={10} stroke="var(--err)" />
          {error}
        </div>
      )}
    </div>
  );
}

function Input({ value, placeholder, mono = false, suffix, error = false, prefix }) {
  return (
    <div
      style={{
        height: 38,
        padding: "0 12px",
        borderRadius: 10,
        background: "var(--bg-ink)",
        border: `1px solid ${error ? "var(--err)" : "var(--line)"}`,
        boxShadow: error ? "0 0 0 3px color-mix(in srgb, var(--err) 14%, transparent)" : "none",
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontFamily: mono ? "var(--font-mono)" : "var(--font-text)",
        fontSize: 13,
      }}
    >
      {prefix && <span style={{ color: "var(--muted)" }}>{prefix}</span>}
      <span style={{ color: value ? "var(--text)" : "var(--muted)", flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {value || placeholder}
      </span>
      {suffix && <Mono size={10} color="var(--muted)">{suffix}</Mono>}
    </div>
  );
}

function Textarea({ value, placeholder, rows = 4, mono = false }) {
  return (
    <div
      style={{
        minHeight: 22 * rows,
        padding: "10px 12px",
        borderRadius: 10,
        background: "var(--bg-ink)",
        border: "1px solid var(--line)",
        fontFamily: mono ? "var(--font-mono)" : "var(--font-text)",
        fontSize: 12.5,
        color: value ? "var(--text)" : "var(--muted)",
        lineHeight: 1.6,
        whiteSpace: "pre-wrap",
      }}
    >
      {value || placeholder}
    </div>
  );
}

function NumberInput({ value, suffix }) {
  return (
    <div
      style={{
        height: 38,
        padding: "0 6px 0 12px",
        borderRadius: 10,
        background: "var(--bg-ink)",
        border: "1px solid var(--line)",
        display: "flex",
        alignItems: "center",
        gap: 6,
        fontFamily: "var(--font-mono)",
        fontSize: 13,
        color: "var(--text)",
        maxWidth: 140,
      }}
    >
      <span style={{ flex: 1 }}>{value}</span>
      {suffix && <Mono size={10} color="var(--muted)">{suffix}</Mono>}
      <div style={{ display: "flex", flexDirection: "column", gap: 1, padding: 2 }}>
        <span style={{ width: 14, height: 14, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)", background: "var(--bg-card)" }}>
          <Icon name="chevron-down" size={8} style={{ transform: "rotate(180deg)" }} />
        </span>
        <span style={{ width: 14, height: 14, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)", background: "var(--bg-card)" }}>
          <Icon name="chevron-down" size={8} />
        </span>
      </div>
    </div>
  );
}

function Select({ value, placeholder }) {
  return (
    <div
      style={{
        height: 38,
        padding: "0 12px",
        borderRadius: 10,
        background: "var(--bg-ink)",
        border: "1px solid var(--line)",
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontFamily: "var(--font-text)",
        fontSize: 13,
        color: value ? "var(--text)" : "var(--muted)",
      }}
    >
      <span style={{ flex: 1, minWidth: 0 }}>{value || placeholder}</span>
      <Icon name="chevron-down" size={13} stroke="var(--muted)" />
    </div>
  );
}

function Toggle({ on = false, label }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
      <span style={{ width: 32, height: 18, borderRadius: 999, background: on ? "var(--ember)" : "var(--bg-ink)", border: `1px solid ${on ? "var(--ember)" : "var(--line)"}`, position: "relative", flexShrink: 0, boxShadow: on ? "0 0 8px color-mix(in srgb, var(--ember) 40%, transparent)" : "none" }}>
        <span style={{ position: "absolute", top: 1, left: on ? 15 : 1, width: 14, height: 14, borderRadius: 999, background: on ? "var(--ember-ink)" : "var(--muted)", transition: "left 0.15s" }} />
      </span>
      {label && <span style={{ fontSize: 13, color: "var(--text)" }}>{label}</span>}
    </div>
  );
}

function Checkbox({ on = false, label, hint }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "flex-start", gap: 10 }}>
      <span
        style={{
          width: 16,
          height: 16,
          borderRadius: 4,
          border: `1.5px solid ${on ? "var(--ember)" : "var(--line)"}`,
          background: on ? "var(--ember)" : "transparent",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        {on && <Icon name="check" size={11} stroke="var(--ember-ink)" strokeWidth={3} />}
      </span>
      <div style={{ lineHeight: 1.3 }}>
        {label && <div style={{ fontSize: 13, color: "var(--text)" }}>{label}</div>}
        {hint && <Mono size={10} color="var(--muted)" style={{ marginTop: 2, display: "block" }}>{hint}</Mono>}
      </div>
    </div>
  );
}

function Radio({ on = false, label, hint }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "flex-start", gap: 10 }}>
      <span
        style={{
          width: 16,
          height: 16,
          borderRadius: 999,
          border: `1.5px solid ${on ? "var(--ember)" : "var(--line)"}`,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        {on && <span style={{ width: 8, height: 8, borderRadius: 999, background: "var(--ember)", boxShadow: "0 0 6px var(--ember-glow)" }} />}
      </span>
      <div style={{ lineHeight: 1.3 }}>
        {label && <div style={{ fontSize: 13, color: "var(--text)" }}>{label}</div>}
        {hint && <Mono size={10} color="var(--muted)" style={{ marginTop: 2, display: "block" }}>{hint}</Mono>}
      </div>
    </div>
  );
}

function Slider({ value = 60, label }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {label && (
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>{label}</Mono>
          <Mono size={11} color="var(--text)">{value}%</Mono>
        </div>
      )}
      <div style={{ height: 6, background: "var(--bg-ink)", borderRadius: 999, position: "relative" }}>
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${value}%`, background: "var(--ember)", borderRadius: 999, boxShadow: "0 0 8px var(--ember-glow)" }} />
        <div style={{ position: "absolute", left: `${value}%`, top: "50%", transform: "translate(-50%, -50%)", width: 14, height: 14, borderRadius: 999, background: "var(--ember-ink)", border: "2px solid var(--ember)", boxShadow: "0 0 0 4px color-mix(in srgb, var(--ember) 14%, transparent)" }} />
      </div>
    </div>
  );
}

function SegmentedControl({ options = [], active = 0 }) {
  return (
    <div style={{ display: "inline-flex", padding: 3, borderRadius: 10, background: "var(--bg-ink)", border: "1px solid var(--line-soft)", gap: 2 }}>
      {options.map((o, i) => (
        <div
          key={i}
          style={{
            padding: "6px 12px",
            borderRadius: 7,
            background: i === active ? "var(--bg-card)" : "transparent",
            color: i === active ? "var(--text)" : "var(--muted)",
            fontSize: 12,
            fontWeight: i === active ? 500 : 400,
            boxShadow: i === active ? "0 1px 0 var(--line-soft)" : "none",
          }}
        >
          {o}
        </div>
      ))}
    </div>
  );
}

Object.assign(window, { FormField, Input, Textarea, NumberInput, Select, Toggle, Checkbox, Radio, Slider, SegmentedControl });
