import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ImagePreview } from "./ImagePreview";

describe("ImagePreview", () => {
  it("renders one thumbnail per url", () => {
    render(<ImagePreview urls={["/a.png", "/b.png"]} />);
    expect(screen.getAllByRole("button", { name: "Ampliar imagem" })).toHaveLength(2);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens the lightbox on click and closes on Escape", () => {
    render(<ImagePreview urls={["/a.png"]} />);
    fireEvent.click(screen.getByRole("button", { name: "Ampliar imagem" }));
    expect(screen.getByRole("dialog", { name: "Visualizador de imagem" })).toBeTruthy();
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders nothing when there are no urls", () => {
    const { container } = render(<ImagePreview urls={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
