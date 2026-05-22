import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar } from "./Avatar";
import { Chip } from "./Chip";
import { Divider } from "./Divider";
import { KBD } from "./KBD";
import { Mono } from "./Mono";
import { NavItem } from "./NavItem";
import { Pulse, StatusDot } from "./StatusDot";
import { SectionLabel } from "./SectionLabel";
import { Tag } from "./Tag";

describe("foundational primitives", () => {
  it("Mono renders monospace text", () => {
    render(<Mono>trace_id</Mono>);
    const el = screen.getByText("trace_id");
    expect(el.className).toContain("font-mono");
  });

  it("Tag renders its content", () => {
    render(<Tag tone="ember">indexado</Tag>);
    expect(screen.getByText("indexado")).toBeTruthy();
  });

  it("Chip renders label and value", () => {
    render(<Chip label="modelo" value="gpt-4o" dot />);
    expect(screen.getByText("modelo")).toBeTruthy();
    expect(screen.getByText("gpt-4o")).toBeTruthy();
  });

  it("KBD renders a <kbd> element", () => {
    render(<KBD>Esc</KBD>);
    const el = screen.getByText("Esc");
    expect(el.tagName).toBe("KBD");
  });

  it("Divider exposes a separator role and orientation", () => {
    const { rerender } = render(<Divider />);
    let sep = screen.getByRole("separator");
    expect(sep.getAttribute("aria-orientation")).toBe("horizontal");
    rerender(<Divider vertical />);
    sep = screen.getByRole("separator");
    expect(sep.getAttribute("aria-orientation")).toBe("vertical");
  });

  it("SectionLabel renders children and an action", () => {
    render(<SectionLabel action={<button type="button">+</button>}>Projetos</SectionLabel>);
    expect(screen.getByText("Projetos")).toBeTruthy();
    expect(screen.getByRole("button", { name: "+" })).toBeTruthy();
  });

  it("Avatar renders JUDITE brand mark with the J glyph", () => {
    render(<Avatar kind="judite" />);
    const el = screen.getByLabelText("JUDITE");
    expect(el.textContent).toBe("J");
  });

  it("Avatar renders a neutral user avatar", () => {
    render(<Avatar kind="user" />);
    expect(screen.getByLabelText("Usuário")).toBeTruthy();
  });

  it("NavItem marks the active item via aria-current", () => {
    const { rerender } = render(<NavItem label="Chat" />);
    expect(screen.getByText("Chat").closest("[aria-current]")).toBeNull();
    rerender(<NavItem label="Chat" active />);
    expect(screen.getByText("Chat").closest('[aria-current="page"]')).toBeTruthy();
  });

  it("StatusDot and Pulse render without crashing", () => {
    const { container: a } = render(<StatusDot pulse />);
    expect(a.firstChild).toBeTruthy();
    const { container: b } = render(<Pulse />);
    expect(b.firstChild).toBeTruthy();
  });
});
