// v4 — shared helpers: tier badges, code refs, bilingual EN/PT subtitle, migration notes

// Tier badge — P1, P2, NEW (re-audit finding), FIX (inconsistência resolution), TOKEN (mapping)
function TierBadge({ tier }) {
  const styles = {
    p1:    { color: "var(--ember)",   label: "P1 · importante",         dot: "var(--ember)" },
    p2:    { color: "var(--azure)",   label: "P2 · qualidade",          dot: "var(--azure)" },
    new:   { color: "var(--amethyst)", label: "Nova descoberta",        dot: "var(--amethyst)" },
    fix:   { color: "var(--ok)",      label: "Inconsistência resolvida", dot: "var(--ok)" },
    token: { color: "var(--muted)",   label: "Token mapping",           dot: "var(--muted)" },
  };
  const s = styles[tier] || styles.p1;
  return (
    <span
      data-v4-tier={tier}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "3px 9px", borderRadius: 999,
        background: `color-mix(in srgb, ${s.color} 12%, transparent)`,
        color: s.color,
        border: `1px solid color-mix(in srgb, ${s.color} 26%, transparent)`,
        fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.12em",
        textTransform: "uppercase", fontWeight: 600, whiteSpace: "nowrap",
      }}
    >
      <span style={{ width: 5, height: 5, borderRadius: 999, background: s.dot, boxShadow: `0 0 6px ${s.dot}` }} />
      {s.label}
    </span>
  );
}

// Code refs block — file:line pointers into web/src
function CodeRefs({ refs = [] }) {
  if (!refs.length) return null;
  return (
    <div data-v4-coderefs style={{ marginTop: 12, padding: "10px 12px", borderRadius: 8, background: "var(--bg-ink)", border: "1px solid var(--line-soft)" }}>
      <Mono size={9.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.16em", display: "block", marginBottom: 6 }}>
        Refs · web/src
      </Mono>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {refs.map((r, i) => (
          <Mono key={i} size={10.5} color="var(--text-soft)">{r}</Mono>
        ))}
      </div>
    </div>
  );
}

// A11y notes — focus, keyboard, ARIA — short bullet list
function A11yNotes({ items = [] }) {
  if (!items.length) return null;
  return (
    <div style={{ marginTop: 12, padding: "10px 12px", borderRadius: 8, background: "color-mix(in srgb, var(--azure) 5%, var(--bg-ink))", border: "1px solid color-mix(in srgb, var(--azure) 22%, transparent)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Icon name="shield" size={11} stroke="var(--azure)" />
        <Mono size={9.5} color="var(--azure)" style={{ textTransform: "uppercase", letterSpacing: "0.16em", fontWeight: 600 }}>
          a11y · focus · keyboard · aria
        </Mono>
      </div>
      <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "var(--text-soft)", lineHeight: 1.6 }}>
        {items.map((item, i) => <li key={i} style={{ marginBottom: 2 }}>{item}</li>)}
      </ul>
    </div>
  );
}

// Migration note — what to change in web/src to comply with the spec
function MigrationNote({ children }) {
  return (
    <div data-v4-migration="true" style={{ marginTop: 12, padding: "10px 12px", borderRadius: 8, background: "color-mix(in srgb, var(--ember) 6%, var(--bg-ink))", border: "1px solid color-mix(in srgb, var(--ember) 28%, transparent)", display: "flex", gap: 10 }}>
      <Icon name="flame" size={12} stroke="var(--ember)" style={{ marginTop: 1, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <Mono size={9.5} color="var(--ember)" style={{ textTransform: "uppercase", letterSpacing: "0.16em", display: "block", marginBottom: 4, fontWeight: 600 }}>
          Migração · web/src
        </Mono>
        <div style={{ fontSize: 12, color: "var(--text-soft)", lineHeight: 1.55 }}>{children}</div>
      </div>
    </div>
  );
}

// Bilingual subtitle (pt-BR primary, EN secondary, italic)
function Bilingual({ pt, en }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span>{pt}</span>
      {en && (
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", color: "var(--muted)", fontSize: "0.95em" }}>
          {en}
        </span>
      )}
    </div>
  );
}

// Extended ComponentSpec wrapper that adds tier badge + code refs + a11y notes + migration
// Wraps ComponentSpec from doc-parts.jsx so we don't duplicate that whole component.
function V4Spec({
  id, name, level, tier, summary, summaryEn,
  props = [], when, code, stack = false, children,
  refs = [], a11y = [], migration,
}) {
  return (
    <div data-v4-spec={tier || "p1"} style={{ marginBottom: 32 }}>
      <ComponentSpec
        id={id}
        name={name}
        level={level}
        summary={summaryEn ? null : summary}
        props={props}
        when={when}
        code={code}
        stack={stack}
      >
        {children}
      </ComponentSpec>

      {/* Optional bilingual summary appears below the card, since ComponentSpec already
          has its own summary slot. Show only when summaryEn is provided. */}
      {summaryEn && (
        <div style={{ marginTop: -24, marginBottom: 12, padding: "12px 16px", background: "var(--bg-ink)", borderLeft: "2px solid var(--line-soft)", fontSize: 13, color: "var(--text-soft)", lineHeight: 1.65 }}>
          <div>{summary}</div>
          <div style={{ marginTop: 4, fontFamily: "var(--font-serif)", fontStyle: "italic", color: "var(--muted)" }}>
            {summaryEn}
          </div>
        </div>
      )}

      {(refs.length > 0 || a11y.length > 0 || migration) && (
        <div data-v4-extras style={{ display: "grid", gridTemplateColumns: a11y.length > 0 && (refs.length > 0 || migration) ? "1fr 1fr" : "1fr", gap: 12 }}>
          {refs.length > 0 && <CodeRefs refs={refs} />}
          {a11y.length > 0 && <A11yNotes items={a11y} />}
          {migration && (
            <div style={{ gridColumn: refs.length > 0 && a11y.length > 0 ? "1 / -1" : "auto" }}>
              <MigrationNote>{migration}</MigrationNote>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { TierBadge, CodeRefs, A11yNotes, MigrationNote, Bilingual, V4Spec });
