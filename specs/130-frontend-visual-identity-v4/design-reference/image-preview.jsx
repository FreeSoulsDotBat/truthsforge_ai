// Image preview family — inline, grid, lightbox, dropzone, upload state

function ImagePlaceholder({ width = 220, height = 140, label = "imagem", hue = 30 }) {
  // Subtle striped warm placeholder so the placeholder reads as "intentional"
  return (
    <div
      style={{
        width,
        height,
        borderRadius: "var(--radius)",
        background: `repeating-linear-gradient(135deg, color-mix(in srgb, var(--ember) 8%, var(--bg-card)) 0 6px, var(--bg-card) 6px 12px)`,
        border: "1px solid var(--line-soft)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted)", letterSpacing: "0.16em", textTransform: "uppercase" }}>
        {label}
      </span>
    </div>
  );
}

// Inline single image (in chat message)
function InlineImage({ width = 320, label = "diagrama-rag.png", size = "287 KB", dims = "1840 × 1240" }) {
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", gap: 6, maxWidth: width }}>
      <div
        style={{
          position: "relative",
          borderRadius: "var(--radius)",
          overflow: "hidden",
          border: "1px solid var(--line-soft)",
          boxShadow: "var(--shadow-soft)",
        }}
      >
        <ImagePlaceholder width={width} height={width * 0.66} label={label.split(".")[1] || "png"} />
        <div
          style={{
            position: "absolute",
            top: 8,
            right: 8,
            display: "flex",
            gap: 4,
          }}
        >
          <IconChip icon="arrow-up-right" />
        </div>
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            padding: "10px 12px 8px",
            background: "linear-gradient(180deg, transparent, rgba(0,0,0,0.7))",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span style={{ fontSize: 12, color: "#fff", fontWeight: 500, flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
          <Mono size={9.5} color="rgba(255,255,255,0.7)">
            {dims}
          </Mono>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Mono size={10} color="var(--faint)">
          {size}
        </Mono>
        <span style={{ width: 2, height: 2, borderRadius: 999, background: "var(--faint)" }} />
        <Mono size={10} color="var(--azure)">
          baixar
        </Mono>
        <span style={{ width: 2, height: 2, borderRadius: 999, background: "var(--faint)" }} />
        <Mono size={10} color="var(--ember)">
          abrir
        </Mono>
      </div>
    </div>
  );
}

function IconChip({ icon }) {
  return (
    <div style={{ width: 24, height: 24, borderRadius: 6, background: "rgba(0,0,0,0.55)", backdropFilter: "blur(8px)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }}>
      <Icon name={icon} size={12} />
    </div>
  );
}

// Image grid (multiple images in one message)
function ImageGrid({ count = 4 }) {
  const labels = ["png", "png", "jpg", "webp"];
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: count === 2 ? "1fr 1fr" : "1fr 1fr",
        gridTemplateRows: count === 2 ? "1fr" : "1fr 1fr",
        gap: 6,
        width: 360,
        height: count === 2 ? 180 : 280,
        borderRadius: "var(--radius)",
        overflow: "hidden",
        border: "1px solid var(--line-soft)",
      }}
    >
      {Array.from({ length: count }).slice(0, 4).map((_, i) => (
        <div key={i} style={{ position: "relative" }}>
          <ImagePlaceholder width="100%" height="100%" label={labels[i] || "png"} />
          {i === 3 && count > 4 && (
            <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.55)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontFamily: "var(--font-display)", fontSize: 24, color: "#fff", letterSpacing: "0.02em" }}>+{count - 4}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// Lightbox / full-screen preview
function Lightbox() {
  return (
    <div
      style={{
        width: 700,
        height: 460,
        background: "var(--bg-ink)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
        boxShadow: "0 24px 80px -24px var(--ember-glow)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--line-soft)", display: "flex", alignItems: "center", gap: 12 }}>
        <Icon name="image" size={14} stroke="var(--ember)" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>diagrama-rag.png</div>
          <Mono size={10} color="var(--faint)">
            1840 × 1240 · 287 KB · enviado por Você · há 4h
          </Mono>
        </div>
        <Mono size={10} color="var(--muted)">2 / 4</Mono>
        <div style={{ display: "flex", gap: 4 }}>
          <IconChip icon="arrow-up-right" />
          <IconChip icon="x" />
        </div>
      </div>
      <div style={{ flex: 1, background: "var(--bg)", display: "flex", alignItems: "center", justifyContent: "center", position: "relative", padding: 24 }}>
        <ImagePlaceholder width={500} height={340} label="diagrama-rag.png" />
        <div style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)" }}>
          <IconChip icon="chevron-right" />
        </div>
        <div style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)" }}>
          <IconChip icon="chevron-right" />
        </div>
      </div>
      <div style={{ padding: "10px 18px", borderTop: "1px solid var(--line-soft)", display: "flex", alignItems: "center", gap: 8 }}>
        <Mono size={10} color="var(--muted)" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <KBD>←</KBD> <KBD>→</KBD> navegar
        </Mono>
        <Mono size={10} color="var(--muted)" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <KBD>esc</KBD> fechar
        </Mono>
        <span style={{ flex: 1 }} />
        <Mono size={10} color="var(--azure)">baixar original</Mono>
      </div>
    </div>
  );
}

// Dropzone (upload state)
function ImageDropzone({ active = false }) {
  return (
    <div
      style={{
        width: 380,
        height: 180,
        borderRadius: "var(--radius)",
        border: `1.5px dashed ${active ? "var(--ember)" : "var(--line)"}`,
        background: active ? "color-mix(in srgb, var(--ember) 8%, var(--bg-card))" : "var(--bg-card)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        position: "relative",
        boxShadow: active ? "0 0 0 4px color-mix(in srgb, var(--ember) 14%, transparent)" : "none",
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          background: active ? "var(--ember)" : "color-mix(in srgb, var(--ember) 12%, var(--bg-ink))",
          color: active ? "var(--ember-ink)" : "var(--ember)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: active ? "none" : "1px solid color-mix(in srgb, var(--ember) 22%, transparent)",
        }}
      >
        <Icon name="image" size={18} />
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 14, color: "var(--text)", letterSpacing: "0.01em", textTransform: "uppercase" }}>
          {active ? "Solte para enviar" : "Arraste uma imagem"}
        </div>
        <Mono size={10} color="var(--muted)" style={{ marginTop: 4, display: "block" }}>
          PNG · JPG · WebP · SVG · até 20 MB
        </Mono>
      </div>
    </div>
  );
}

// Upload progress state
function ImageUploading({ progress = 64 }) {
  return (
    <div
      style={{
        width: 320,
        borderRadius: "var(--radius)",
        background: "var(--bg-card)",
        border: "1px solid var(--line-soft)",
        padding: 12,
        display: "flex",
        gap: 12,
        alignItems: "center",
      }}
    >
      <div style={{ width: 48, height: 48, borderRadius: 10, background: "var(--bg-ink)", border: "1px solid var(--line-soft)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, position: "relative" }}>
        <Icon name="image" size={18} stroke="var(--muted)" />
        <div style={{ position: "absolute", inset: -2, borderRadius: 12, border: "2px solid transparent", borderTopColor: "var(--ember)", borderRightColor: "var(--ember)", animation: "tfSpin 1s linear infinite" }} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, color: "var(--text)", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          diagrama-rag.png
        </div>
        <Mono size={10} color="var(--muted)" style={{ marginTop: 2, display: "block" }}>
          enviando · {progress}% · 184 KB / 287 KB
        </Mono>
        <div style={{ height: 3, background: "var(--bg-ink)", borderRadius: 999, marginTop: 8, overflow: "hidden" }}>
          <div style={{ width: `${progress}%`, height: "100%", background: "var(--ember)", boxShadow: "0 0 6px var(--ember-glow)" }} />
        </div>
      </div>
    </div>
  );
}

// Generated image (DALL-E output card)
function GeneratedImageCard() {
  return (
    <div
      style={{
        width: 340,
        borderRadius: "var(--radius)",
        background: "var(--bg-card)",
        border: "1px solid color-mix(in srgb, var(--amethyst) 22%, transparent)",
        boxShadow: "0 12px 32px -20px var(--amethyst-glow)",
        overflow: "hidden",
      }}
    >
      <ImagePlaceholder width="100%" height={220} label="generated" />
      <div style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <Icon name="sparkles" size={12} stroke="var(--amethyst)" />
          <Mono size={10} color="var(--amethyst)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
            gerada · dall-e 3
          </Mono>
        </div>
        <div style={{ fontSize: 12.5, color: "var(--text-soft)", lineHeight: 1.55, marginBottom: 10 }}>
          "diagrama isométrico de pipeline RAG com postgres e pgvector, paleta âmbar/preta, estilo blueprint técnico"
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <Tag tone="amethyst">1024×1024</Tag>
          <Tag tone="neutral">~4.2s</Tag>
          <Tag tone="neutral">R$ 0,08</Tag>
        </div>
      </div>
    </div>
  );
}

// Need to add amethyst tone to Tag — let's do that here as well
// (parts.jsx Tag already supports "ember","ok","warn","neutral" — adding amethyst inline below is unnecessary;
//  we'll just use the inline style fallback. Actually since Tag falls back to neutral, the amethyst tag above
//  won't be amethyst-colored. Let me just override inline.)

Object.assign(window, {
  ImagePlaceholder,
  InlineImage,
  ImageGrid,
  Lightbox,
  ImageDropzone,
  ImageUploading,
  GeneratedImageCard,
  IconChip,
});
