"use client";

import React, { useState, useMemo } from "react";
import { useEditor, EditorContent, type JSONContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import LinkExtension from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import {
  Heading1,
  Heading2,
  Heading3,
  Heading4,
  Bold,
  Italic,
  Code,
  List,
  ListOrdered,
  Quote,
  Link2,
  Undo,
  Redo,
  AlertTriangle,
  X,
  Search,
  Type,
  FileCode,
} from "lucide-react";

interface StructuredEditorProps {
  initialContent?: string;
  initialStructuredContent?: JSONContent | null;
  onChange: (ast: JSONContent, markdown: string) => void;
  availableSlugs?: Array<{ slug: string; title: string }>;
}

/**
 * Convert TipTap JSON AST to clean Markdown text for legacy storage and BM25F indexing.
 */
export function astToMarkdown(node: JSONContent): string {
  if (!node) return "";

  if (node.type === "doc") {
    return (node.content || []).map((child: JSONContent) => astToMarkdown(child)).join("\n\n");
  }

  if (node.type === "heading") {
    const level = node.attrs?.level || 1;
    const hashes = "#".repeat(level);
    const text = (node.content || []).map((c: JSONContent) => renderInline(c)).join("");
    return `${hashes} ${text}`;
  }

  if (node.type === "paragraph") {
    return (node.content || []).map((c: JSONContent) => renderInline(c)).join("");
  }

  if (node.type === "blockquote") {
    const inner = (node.content || []).map((c: JSONContent) => astToMarkdown(c)).join("\n");
    return inner.split("\n").map((line: string) => `> ${line}`).join("\n");
  }

  if (node.type === "codeBlock") {
    const lang = node.attrs?.language || "";
    const codeText = (node.content || []).map((c: JSONContent) => c.text || "").join("");
    return `\`\`\`${lang}\n${codeText}\n\`\`\``;
  }

  if (node.type === "bulletList") {
    return (node.content || [])
      .map((item: JSONContent) => {
        const itemText = (item.content || []).map((c: JSONContent) => astToMarkdown(c)).join(" ");
        return `- ${itemText}`;
      })
      .join("\n");
  }

  if (node.type === "orderedList") {
    return (node.content || [])
      .map((item: JSONContent, idx: number) => {
        const itemText = (item.content || []).map((c: JSONContent) => astToMarkdown(c)).join(" ");
        return `${idx + 1}. ${itemText}`;
      })
      .join("\n");
  }

  return "";
}

function renderInline(node: JSONContent): string {
  if (!node) return "";
  let text = node.text || "";
  if (!node.marks) return text;

  for (const mark of node.marks) {
    if (mark.type === "bold") {
      text = `**${text}**`;
    } else if (mark.type === "italic") {
      text = `*${text}*`;
    } else if (mark.type === "code") {
      text = `\`${text}\``;
    } else if (mark.type === "link") {
      const href = mark.attrs?.href || "#";
      text = `[${text}](${href})`;
    }
  }
  return text;
}

export const StructuredEditor: React.FC<StructuredEditorProps> = ({
  initialContent = "",
  initialStructuredContent,
  onChange,
  availableSlugs = [],
}) => {
  const [h1Count, setH1Count] = useState(0);
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkQuery, setLinkQuery] = useState("");
  const [linkUrl, setLinkUrl] = useState("");

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3, 4],
        },
      }),
      LinkExtension.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: "text-sky-400 underline hover:text-sky-300 font-medium",
        },
      }),
      Placeholder.configure({
        placeholder: "Write structured knowledge here...",
      }),
    ],
    editorProps: {
      attributes: {
        class: "tiptap focus:outline-none p-5 min-h-[360px] text-slate-200",
      },
    },
    content: initialStructuredContent || initialContent || "<p></p>",
    immediatelyRender: false,
    onCreate: ({ editor }) => {
      setH1Count((editor.getJSON().content || []).filter(node => node.type === "heading" && node.attrs?.level === 1).length);
    },
    onUpdate: ({ editor }) => {
      const json = editor.getJSON();
      const markdown = astToMarkdown(json);

      // Count H1 nodes
      let count = 0;
      for (const node of json.content || []) {
        if (node.type === "heading" && node.attrs?.level === 1) {
          count++;
        }
      }
      setH1Count(count);

      onChange(json, markdown);
    },
  });

  // Determine current block description based on cursor position
  const currentBlockType = useMemo(() => {
    if (!editor) return "Paragraph";
    if (editor.isActive("heading", { level: 1 })) return "H1 Page Heading";
    if (editor.isActive("heading", { level: 2 })) return "H2 Major Section";
    if (editor.isActive("heading", { level: 3 })) return "H3 Subsection";
    if (editor.isActive("heading", { level: 4 })) return "H4 Nested Heading";
    if (editor.isActive("bulletList")) return "Bullet List";
    if (editor.isActive("orderedList")) return "Ordered List";
    if (editor.isActive("blockquote")) return "Blockquote";
    if (editor.isActive("codeBlock")) return "Code Block";
    return "Body Paragraph";
  }, [editor, editor?.state.selection]);

  if (!editor) {
    return (
      <div className="h-64 flex items-center justify-center bg-slate-950 border border-slate-800 rounded-xl text-slate-500 font-mono text-xs">
        Initializing Knowledge AST Engine...
      </div>
    );
  }

  const handleApplyLink = (url: string) => {
    if (!url) {
      editor.chain().focus().unsetLink().run();
    } else {
      editor.chain().focus().setLink({ href: url }).run();
    }
    setShowLinkModal(false);
    setLinkUrl("");
    setLinkQuery("");
  };

  const filteredSlugs = availableSlugs.filter(
    (s) =>
      s.title.toLowerCase().includes(linkQuery.toLowerCase()) ||
      s.slug.toLowerCase().includes(linkQuery.toLowerCase())
  );

  return (
    <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950 shadow-sm">
      {/* Multiple H1 Structural Warning */}
      {h1Count > 1 && (
        <div className="bg-amber-950/40 border-b border-amber-800/60 px-4 py-2.5 flex items-center gap-2 text-xs text-amber-300">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            <strong>Semantic Hierarchy Notice:</strong> Document contains {h1Count} Heading 1 blocks.
            A single primary H1 heading preserves optimal BM25F title-heading field signals.
          </span>
        </div>
      )}

      {/* Editor Toolbar with Grouping & Active Indicator */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-slate-900 border-b border-slate-800 text-slate-300 select-none">
        <div className="flex flex-wrap items-center gap-1">
          {/* GROUP 1: HEADINGS */}
          <div className="flex items-center gap-0.5" role="group" aria-label="Headings">
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
              aria-pressed={editor.isActive("heading", { level: 1 })}
              className={`px-2 py-1 rounded text-xs font-bold transition-all flex items-center gap-1 border ${
                editor.isActive("heading", { level: 1 })
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Heading 1 (# + Space)"
            >
              <Heading1 className="w-4 h-4" />
              <span className="text-[10px] font-mono">H1</span>
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
              aria-pressed={editor.isActive("heading", { level: 2 })}
              className={`px-2 py-1 rounded text-xs font-bold transition-all flex items-center gap-1 border ${
                editor.isActive("heading", { level: 2 })
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Heading 2 (## + Space)"
            >
              <Heading2 className="w-4 h-4" />
              <span className="text-[10px] font-mono">H2</span>
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
              aria-pressed={editor.isActive("heading", { level: 3 })}
              className={`px-2 py-1 rounded text-xs font-bold transition-all flex items-center gap-1 border ${
                editor.isActive("heading", { level: 3 })
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Heading 3 (### + Space)"
            >
              <Heading3 className="w-4 h-4" />
              <span className="text-[10px] font-mono">H3</span>
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleHeading({ level: 4 }).run()}
              aria-pressed={editor.isActive("heading", { level: 4 })}
              className={`px-2 py-1 rounded text-xs font-bold transition-all flex items-center gap-1 border ${
                editor.isActive("heading", { level: 4 })
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Heading 4 (#### + Space)"
            >
              <Heading4 className="w-4 h-4" />
              <span className="text-[10px] font-mono">H4</span>
            </button>
          </div>

          <div className="h-5 w-px bg-slate-800 mx-1.5" />

          {/* GROUP 2: INLINE FORMATTING */}
          <div className="flex items-center gap-0.5" role="group" aria-label="Inline Styles">
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleBold().run()}
              aria-pressed={editor.isActive("bold")}
              className={`p-1.5 rounded transition-all border ${
                editor.isActive("bold")
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Bold (Ctrl+B)"
            >
              <Bold className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleItalic().run()}
              aria-pressed={editor.isActive("italic")}
              className={`p-1.5 rounded transition-all border ${
                editor.isActive("italic")
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Italic (Ctrl+I)"
            >
              <Italic className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleCode().run()}
              aria-pressed={editor.isActive("code")}
              className={`p-1.5 rounded transition-all border ${
                editor.isActive("code")
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Inline Code (`code`)"
            >
              <Code className="w-4 h-4" />
            </button>
          </div>

          <div className="h-5 w-px bg-slate-800 mx-1.5" />

          {/* GROUP 3: STRUCTURAL BLOCKS */}
          <div className="flex items-center gap-0.5" role="group" aria-label="Lists and Blocks">
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleBulletList().run()}
              aria-pressed={editor.isActive("bulletList")}
              className={`p-1.5 rounded transition-all border ${
                editor.isActive("bulletList")
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Bullet List (- + Space)"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleOrderedList().run()}
              aria-pressed={editor.isActive("orderedList")}
              className={`p-1.5 rounded transition-all border ${
                editor.isActive("orderedList")
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Ordered List (1. + Space)"
            >
              <ListOrdered className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleBlockquote().run()}
              aria-pressed={editor.isActive("blockquote")}
              className={`p-1.5 rounded transition-all border ${
                editor.isActive("blockquote")
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Blockquote (> + Space)"
            >
              <Quote className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().toggleCodeBlock().run()}
              aria-pressed={editor.isActive("codeBlock")}
              className={`p-1.5 rounded transition-all border ${
                editor.isActive("codeBlock")
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Code Block (``` + Space)"
            >
              <FileCode className="w-4 h-4" />
            </button>
          </div>

          <div className="h-5 w-px bg-slate-800 mx-1.5" />

          {/* GROUP 4: INTERNAL LINKING */}
          <div className="flex items-center gap-0.5" role="group" aria-label="Linking">
            <button
              type="button"
              onClick={() => {
                const previousUrl = editor.getAttributes("link").href || "";
                setLinkUrl(previousUrl);
                setShowLinkModal(true);
              }}
              aria-pressed={editor.isActive("link")}
              className={`p-1.5 rounded transition-all border ${
                editor.isActive("link")
                  ? "bg-sky-500/25 border-sky-400/80 text-sky-300 shadow-sm"
                  : "border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
              title="Internal Document Link"
            >
              <Link2 className="w-4 h-4" />
            </button>
          </div>

          <div className="h-5 w-px bg-slate-800 mx-1.5" />

          {/* GROUP 5: HISTORY */}
          <div className="flex items-center gap-0.5" role="group" aria-label="History">
            <button
              type="button"
              onClick={() => editor.chain().focus().undo().run()}
              disabled={!editor.can().undo()}
              className="p-1.5 rounded transition-colors text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:opacity-25"
              title="Undo (Ctrl+Z)"
            >
              <Undo className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => editor.chain().focus().redo().run()}
              disabled={!editor.can().redo()}
              className="p-1.5 rounded transition-colors text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:opacity-25"
              title="Redo (Ctrl+Shift+Z)"
            >
              <Redo className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* CURRENT BLOCK INDICATOR BADGE */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 shadow-inner">
            <Type className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400 font-sans">Block:</span>
            <span className="font-semibold text-sky-300">{currentBlockType}</span>
          </div>
        </div>
      </div>

      {/* Editor Content Canvas */}
      <div className="bg-slate-950">
        <EditorContent editor={editor} />
      </div>

      {/* Link Picker Modal */}
      {showLinkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Link2 className="w-4 h-4 text-sky-400" />
                <span>Insert Link / Knowledge Graph Connection</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowLinkModal(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-400 block mb-1">
                  Custom URL or Path
                </label>
                <input
                  type="text"
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                  placeholder="/doc/my-bicycle-story or https://..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-md px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 font-mono"
                />
              </div>

              {availableSlugs.length > 0 && (
                <div>
                  <label className="text-xs font-medium text-slate-400 block mb-1">
                    Or select an existing document:
                  </label>
                  <div className="relative mb-2">
                    <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                    <input
                      type="text"
                      value={linkQuery}
                      onChange={(e) => setLinkQuery(e.target.value)}
                      placeholder="Filter documents..."
                      className="w-full bg-slate-950 border border-slate-800 rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                    />
                  </div>
                  <div className="max-h-40 overflow-y-auto space-y-1 pr-1 border border-slate-800/80 rounded-md p-1 bg-slate-950/60">
                    {filteredSlugs.map((s) => (
                      <button
                        key={s.slug}
                        type="button"
                        onClick={() => setLinkUrl(`/doc/${s.slug}`)}
                        className={`w-full text-left px-2.5 py-1.5 rounded text-xs flex items-center justify-between transition-colors ${
                          linkUrl === `/doc/${s.slug}`
                            ? "bg-sky-500/20 text-sky-300 font-medium"
                            : "hover:bg-slate-800/70 text-slate-300"
                        }`}
                      >
                        <span className="truncate">{s.title}</span>
                        <span className="text-[10px] font-mono text-slate-500 ml-2">/doc/{s.slug}</span>
                      </button>
                    ))}
                    {filteredSlugs.length === 0 && (
                      <div className="text-center py-3 text-xs text-slate-500">
                        No matching documents found
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowLinkModal(false)}
                  className="px-3 py-1.5 rounded text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleApplyLink(linkUrl)}
                  className="px-4 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs shadow-sm"
                >
                  Apply Link
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
