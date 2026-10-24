import React from "react";
import Link from "next/link";

interface MarkdownProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownProps> = ({ content }) => {
  if (!content) return null;

  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let codeLanguage = "";

  const renderInline = (text: string): React.ReactNode => {
    // Replace links: [label](/doc/slug)
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = linkRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(renderFormatting(text.substring(lastIndex, match.index)));
      }
      const label = match[1];
      const href = match[2];
      const isInternal = href.startsWith("/doc/") || href.startsWith("/doc?") || href.startsWith("./") || !href.includes("://");
      let cleanHref = href;
      if (isInternal) {
        if (href.startsWith("/doc?")) {
          cleanHref = href;
        } else if (href.startsWith("/doc/")) {
          cleanHref = `/doc?slug=${encodeURIComponent(href.replace("/doc/", ""))}`;
        } else if (href.startsWith("./")) {
          cleanHref = `/doc?slug=${encodeURIComponent(href.replace("./", ""))}`;
        } else if (!href.includes("://")) {
          cleanHref = `/doc?slug=${encodeURIComponent(href.replace(/^\/+/, ""))}`;
        }
      }

      if (isInternal) {
        parts.push(
          <Link
            key={match.index}
            href={cleanHref}
            className="text-blue-600 dark:text-blue-400 underline decoration-blue-300 dark:decoration-blue-700 underline-offset-2 hover:text-blue-800 dark:hover:text-blue-300 font-medium transition-colors"
          >
            {label}
          </Link>
        );
      } else {
        parts.push(
          <a
            key={match.index}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400 underline underline-offset-2 hover:text-blue-800 dark:hover:text-blue-300"
          >
            {label}
          </a>
        );
      }
      lastIndex = linkRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(renderFormatting(text.substring(lastIndex)));
    }

    return parts.length > 0 ? parts : text;
  };

  const renderFormatting = (text: string): React.ReactNode => {
    // Handle inline code `code`
    const codeRegex = /`([^`]+)`/g;
    const codeParts: React.ReactNode[] = [];
    let lastIdx = 0;
    let cMatch;

    while ((cMatch = codeRegex.exec(text)) !== null) {
      if (cMatch.index > lastIdx) {
        codeParts.push(renderBoldItalic(text.substring(lastIdx, cMatch.index)));
      }
      codeParts.push(
        <code
          key={`code-${cMatch.index}`}
          className="bg-neutral-100 dark:bg-neutral-800 text-rose-600 dark:text-rose-400 px-1.5 py-0.5 rounded text-sm font-mono"
        >
          {cMatch[1]}
        </code>
      );
      lastIdx = codeRegex.lastIndex;
    }
    if (lastIdx < text.length) {
      codeParts.push(renderBoldItalic(text.substring(lastIdx)));
    }
    return codeParts.length > 0 ? codeParts : text;
  };

  const renderBoldItalic = (text: string): React.ReactNode => {
    // Bold **text**
    const boldRegex = /\*\*([^*]+)\*\*/g;
    const parts: React.ReactNode[] = [];
    let last = 0;
    let bMatch;

    while ((bMatch = boldRegex.exec(text)) !== null) {
      if (bMatch.index > last) {
        parts.push(text.substring(last, bMatch.index));
      }
      parts.push(
        <strong key={`b-${bMatch.index}`} className="font-semibold text-neutral-900 dark:text-neutral-100">
          {bMatch[1]}
        </strong>
      );
      last = boldRegex.lastIndex;
    }
    if (last < text.length) {
      parts.push(text.substring(last));
    }
    return parts.length > 0 ? parts : text;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block check
    if (line.trim().startsWith("```")) {
      if (inCodeBlock) {
        elements.push(
          <div key={`codeblock-${i}`} className="my-4 rounded-lg overflow-hidden bg-neutral-900 text-neutral-100 p-4 font-mono text-sm border border-neutral-800">
            <pre className="overflow-x-auto">{codeBuffer.join("\n")}</pre>
          </div>
        );
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
        codeLanguage = line.trim().replace("```", "").trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    const trimmed = line.trim();

    // Empty line
    if (!trimmed) {
      elements.push(<div key={`spacer-${i}`} className="h-3" />);
      continue;
    }

    // Headings
    if (trimmed.startsWith("# ")) {
      elements.push(
        <h1 key={`h1-${i}`} className="text-3xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50 mt-6 mb-4 pb-2 border-b border-neutral-200 dark:border-neutral-800">
          {trimmed.replace("# ", "")}
        </h1>
      );
    } else if (trimmed.startsWith("## ")) {
      elements.push(
        <h2 key={`h2-${i}`} className="text-xl font-bold tracking-tight text-neutral-800 dark:text-neutral-100 mt-6 mb-3">
          {trimmed.replace("## ", "")}
        </h2>
      );
    } else if (trimmed.startsWith("### ")) {
      elements.push(
        <h3 key={`h3-${i}`} className="text-lg font-semibold text-neutral-800 dark:text-neutral-200 mt-4 mb-2">
          {trimmed.replace("### ", "")}
        </h3>
      );
    } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      elements.push(
        <li key={`li-${i}`} className="ml-6 list-disc text-neutral-700 dark:text-neutral-300 leading-relaxed my-1">
          {renderInline(trimmed.substring(2))}
        </li>
      );
    } else if (/^\d+\.\s/.test(trimmed)) {
      const match = trimmed.match(/^(\d+)\.\s(.*)$/);
      elements.push(
        <li key={`oli-${i}`} className="ml-6 list-decimal text-neutral-700 dark:text-neutral-300 leading-relaxed my-1">
          {renderInline(match ? match[2] : trimmed)}
        </li>
      );
    } else if (trimmed.startsWith("> ")) {
      elements.push(
        <blockquote key={`quote-${i}`} className="border-l-4 border-amber-500 pl-4 py-1 my-3 bg-amber-50/50 dark:bg-amber-950/20 text-neutral-800 dark:text-neutral-200 italic">
          {renderInline(trimmed.substring(2))}
        </blockquote>
      );
    } else {
      elements.push(
        <p key={`p-${i}`} className="text-neutral-700 dark:text-neutral-300 leading-relaxed my-2 text-[15px]">
          {renderInline(line)}
        </p>
      );
    }
  }

  return <div className="pese-markdown space-y-1">{elements}</div>;
};
