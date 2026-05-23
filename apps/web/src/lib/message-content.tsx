import { Fragment, type ReactNode } from "react";

import { CodeBlock } from "./code-block";

const imageMarkdownPatternSource =
  "!\\[[^\\]]*\\]\\((data:image\\/[^)\\s]+|https?:\\/\\/[^)\\s]+|blob:[^)\\s]+|\\/[^)\\s]+)\\)";
const markdownLinkPattern = /\[([^\]]+)]\((https?:\/\/[^)\s]+)\)/g;
const inlineTokenPattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+]\((https?:\/\/[^)\s]+)\)|\*[^*]+\*)/g;
const markdownLinkWholePattern = /^\[([^\]]+)]\((https?:\/\/[^)\s]+)\)$/;
const headingPattern = /^(#{1,6})\s+(.+)$/;
const unorderedListPattern = /^\s*[-*]\s+(.+)$/;
const orderedListPattern = /^\s*\d+\.\s+(.+)$/;
const quotePattern = /^\s*>\s?(.*)$/;
const fenceStartPattern = /^\s*```/;

export function imageUrlFromMarkdown(content: string): string | null {
  return imageUrlsFromMarkdown(content)[0] ?? null;
}

export function imageUrlsFromMarkdown(content: string): string[] {
  return [...content.matchAll(new RegExp(imageMarkdownPatternSource, "g"))].map((match) => match[1]);
}

export function stripImageMarkdown(content: string): string {
  return content
    .replace(new RegExp(imageMarkdownPatternSource, "g"), "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function renderLinkedText(content: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let cursor = 0;

  for (const match of content.matchAll(markdownLinkPattern)) {
    const index = match.index ?? 0;
    if (index > cursor) nodes.push(content.slice(cursor, index));
    nodes.push(
      <a
        key={`${match[2]}:${index}`}
        href={match[2]}
        target="_blank"
        rel="noreferrer"
        className="text-forge-amber underline decoration-forge-amber/50 underline-offset-2"
      >
        {match[1]}
      </a>
    );
    cursor = index + match[0].length;
  }

  if (cursor < content.length) nodes.push(content.slice(cursor));
  return nodes.length ? nodes : [content];
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let tokenIndex = 0;

  for (const match of text.matchAll(inlineTokenPattern)) {
    const index = match.index ?? 0;
    const token = match[0];
    if (index > cursor) nodes.push(text.slice(cursor, index));
    cursor = index + token.length;

    const linkMatch = token.match(markdownLinkWholePattern);
    if (linkMatch) {
      nodes.push(
        <a
          key={`${keyPrefix}:link:${tokenIndex}`}
          href={linkMatch[2]}
          target="_blank"
          rel="noreferrer"
          className="text-forge-amber underline decoration-forge-amber/50 underline-offset-2"
        >
          {linkMatch[1]}
        </a>
      );
      tokenIndex += 1;
      continue;
    }

    if (token.startsWith("**") && token.endsWith("**")) {
      nodes.push(<strong key={`${keyPrefix}:strong:${tokenIndex}`}>{token.slice(2, -2)}</strong>);
      tokenIndex += 1;
      continue;
    }

    if (token.startsWith("*") && token.endsWith("*")) {
      nodes.push(<em key={`${keyPrefix}:em:${tokenIndex}`}>{token.slice(1, -1)}</em>);
      tokenIndex += 1;
      continue;
    }

    if (token.startsWith("`") && token.endsWith("`")) {
      nodes.push(
        <code
          key={`${keyPrefix}:code:${tokenIndex}`}
          className="rounded bg-forge-ink-deep px-1.5 py-0.5 font-mono text-xs text-forge-amber"
        >
          {token.slice(1, -1)}
        </code>
      );
      tokenIndex += 1;
      continue;
    }

    nodes.push(token);
    tokenIndex += 1;
  }

  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes.length ? nodes : [text];
}

function renderParagraph(lines: string[], keyPrefix: string): ReactNode {
  return (
    <p key={`${keyPrefix}:paragraph`} className="mb-3 whitespace-pre-wrap leading-6 text-forge-text">
      {lines.map((line, lineIndex) => (
        <Fragment key={`${keyPrefix}:line:${lineIndex}`}>
          {lineIndex > 0 ? <br /> : null}
          {renderInline(line, `${keyPrefix}:inline:${lineIndex}`)}
        </Fragment>
      ))}
    </p>
  );
}

function isBlockBoundary(line: string): boolean {
  return (
    headingPattern.test(line) ||
    unorderedListPattern.test(line) ||
    orderedListPattern.test(line) ||
    quotePattern.test(line) ||
    fenceStartPattern.test(line)
  );
}

export function renderMarkdown(content: string): ReactNode {
  const normalized = content.replace(/\r\n/g, "\n").trimEnd();
  if (!normalized) return null;

  const lines = normalized.split("\n");
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let blockIndex = 0;

  while (cursor < lines.length) {
    const line = lines[cursor];
    const trimmed = line.trim();

    if (!trimmed) {
      cursor += 1;
      continue;
    }

    if (fenceStartPattern.test(line)) {
      const lang = line.replace(/^\s*```/, "").trim();
      cursor += 1;
      const codeLines: string[] = [];
      while (cursor < lines.length && !fenceStartPattern.test(lines[cursor])) {
        codeLines.push(lines[cursor]);
        cursor += 1;
      }
      if (cursor < lines.length) cursor += 1;
      nodes.push(<CodeBlock key={`block:${blockIndex}:code`} lang={lang} code={codeLines.join("\n")} />);
      blockIndex += 1;
      continue;
    }

    const headingMatch = line.match(headingPattern);
    if (headingMatch) {
      const level = Math.min(6, headingMatch[1].length);
      const headingText = headingMatch[2].trim();
      const classByLevel: Record<number, string> = {
        1: "mb-3 text-2xl font-semibold",
        2: "mb-3 text-xl font-semibold",
        3: "mb-2 text-lg font-semibold",
        4: "mb-2 text-base font-semibold",
        5: "mb-2 text-sm font-semibold",
        6: "mb-2 text-sm font-medium"
      };
      const headingClass = classByLevel[level] ?? classByLevel[6];
      const headingNode =
        level === 1 ? (
          <h1 key={`block:${blockIndex}:h1`} className={headingClass}>
            {renderInline(headingText, `block:${blockIndex}:heading`)}
          </h1>
        ) : level === 2 ? (
          <h2 key={`block:${blockIndex}:h2`} className={headingClass}>
            {renderInline(headingText, `block:${blockIndex}:heading`)}
          </h2>
        ) : level === 3 ? (
          <h3 key={`block:${blockIndex}:h3`} className={headingClass}>
            {renderInline(headingText, `block:${blockIndex}:heading`)}
          </h3>
        ) : level === 4 ? (
          <h4 key={`block:${blockIndex}:h4`} className={headingClass}>
            {renderInline(headingText, `block:${blockIndex}:heading`)}
          </h4>
        ) : level === 5 ? (
          <h5 key={`block:${blockIndex}:h5`} className={headingClass}>
            {renderInline(headingText, `block:${blockIndex}:heading`)}
          </h5>
        ) : (
          <h6 key={`block:${blockIndex}:h6`} className={headingClass}>
            {renderInline(headingText, `block:${blockIndex}:heading`)}
          </h6>
        );
      nodes.push(headingNode);
      cursor += 1;
      blockIndex += 1;
      continue;
    }

    if (unorderedListPattern.test(line)) {
      const items: ReactNode[] = [];
      while (cursor < lines.length) {
        const match = lines[cursor].match(unorderedListPattern);
        if (!match) break;
        items.push(
          <li key={`block:${blockIndex}:ul:item:${items.length}`} className="ml-5 list-disc">
            {renderInline(match[1].trim(), `block:${blockIndex}:ul:inline:${items.length}`)}
          </li>
        );
        cursor += 1;
      }
      nodes.push(
        <ul key={`block:${blockIndex}:ul`} className="mb-3 space-y-1">
          {items}
        </ul>
      );
      blockIndex += 1;
      continue;
    }

    if (orderedListPattern.test(line)) {
      const items: ReactNode[] = [];
      while (cursor < lines.length) {
        const match = lines[cursor].match(orderedListPattern);
        if (!match) break;
        items.push(
          <li key={`block:${blockIndex}:ol:item:${items.length}`} className="ml-5 list-decimal">
            {renderInline(match[1].trim(), `block:${blockIndex}:ol:inline:${items.length}`)}
          </li>
        );
        cursor += 1;
      }
      nodes.push(
        <ol key={`block:${blockIndex}:ol`} className="mb-3 space-y-1">
          {items}
        </ol>
      );
      blockIndex += 1;
      continue;
    }

    if (quotePattern.test(line)) {
      const quoteLines: string[] = [];
      while (cursor < lines.length) {
        const match = lines[cursor].match(quotePattern);
        if (!match) break;
        quoteLines.push(match[1]);
        cursor += 1;
      }
      nodes.push(
        <blockquote
          key={`block:${blockIndex}:quote`}
          className="mb-3 border-l-2 border-forge-amber/60 pl-3 text-forge-muted"
        >
          {quoteLines.map((quoteLine, quoteIndex) => (
            <Fragment key={`block:${blockIndex}:quote:line:${quoteIndex}`}>
              {quoteIndex > 0 ? <br /> : null}
              {renderInline(quoteLine, `block:${blockIndex}:quote:inline:${quoteIndex}`)}
            </Fragment>
          ))}
        </blockquote>
      );
      blockIndex += 1;
      continue;
    }

    const paragraphLines = [line];
    cursor += 1;
    while (cursor < lines.length && lines[cursor].trim() && !isBlockBoundary(lines[cursor])) {
      paragraphLines.push(lines[cursor]);
      cursor += 1;
    }
    nodes.push(renderParagraph(paragraphLines, `block:${blockIndex}`));
    blockIndex += 1;
  }

  return <>{nodes}</>;
}
