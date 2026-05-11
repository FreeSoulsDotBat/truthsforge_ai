import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  imageUrlFromMarkdown,
  imageUrlsFromMarkdown,
  renderLinkedText,
  renderMarkdown,
  stripImageMarkdown
} from "./message-content";

describe("message content helpers", () => {
  it("extracts generated image urls from markdown", () => {
    expect(imageUrlFromMarkdown("![Imagem gerada](https://example.com/image.png)")).toBe(
      "https://example.com/image.png"
    );
  });

  it("returns null when there is no generated image markdown", () => {
    expect(imageUrlFromMarkdown("resposta normal")).toBeNull();
  });

  it("extracts multiple image urls including relative paths", () => {
    expect(
      imageUrlsFromMarkdown("![Imagem A](/api/files/file_a/content)\n![Imagem B](https://example.com/image-b.png)")
    ).toEqual(["/api/files/file_a/content", "https://example.com/image-b.png"]);
  });

  it("strips image markdown from content while preserving text", () => {
    expect(stripImageMarkdown("Texto antes\n![Imagem](/api/files/file_a/content)\nTexto depois")).toBe(
      "Texto antes\n\nTexto depois"
    );
  });

  it("renders markdown links as safe external anchors", () => {
    const { getByRole } = render(<p>{renderLinkedText("Fonte: [OpenAI](https://openai.com)")}</p>);
    const link = getByRole("link", { name: "OpenAI" });

    expect(link).toHaveAttribute("href", "https://openai.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("renders headings, lists and emphasis from markdown", () => {
    const { getByRole, getByText } = render(
      <div>{renderMarkdown("### Título\n\n- **Item**\n- segundo\n\nUse `codigo` aqui.")}</div>
    );

    expect(getByRole("heading", { level: 3, name: "Título" })).toBeInTheDocument();
    expect(getByText("Item", { selector: "strong" })).toBeInTheDocument();
    expect(getByText("codigo", { selector: "code" })).toBeInTheDocument();
  });
});
