"use client";

import type { JSONContent } from "@tiptap/react";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { saveDocument, getDocuments, DocumentData, FAQItem } from "@/lib/api";
import { MarkdownRenderer } from "@/lib/markdown";
import { StructuredEditor } from "./StructuredEditor";
import {
  ArrowLeft,
  Save,
  Eye,
  Edit3,
  Send,
  CheckCircle,
  AlertCircle,
  Plus,
  Trash2,
  ChevronUp,
  ChevronDown,
  HelpCircle,
  Code2,
} from "lucide-react";

interface DocumentEditorFormProps {
  initialData?: Partial<DocumentData>;
  isNew?: boolean;
}

export const DocumentEditorForm: React.FC<DocumentEditorFormProps> = ({
  initialData,
  isNew = false,
}) => {
  const router = useRouter();

  const [title, setTitle] = useState(initialData?.title || "");
  const [slug, setSlug] = useState(initialData?.slug || "");
  const [metaDescription, setMetaDescription] = useState(initialData?.meta_description || "");
  const [content, setContent] = useState(initialData?.content || "");
  const [structuredContent, setStructuredContent] = useState<JSONContent | null>(
    initialData?.structured_content || null
  );
  const [faqs, setFaqs] = useState<FAQItem[]>(initialData?.faqs || []);
  const [collapsedFaqs, setCollapsedFaqs] = useState<Record<string, boolean>>({});
  const [keywords, setKeywords] = useState(initialData?.keywords?.join(", ") || "");
  const headings = initialData?.headings?.join(", ") || "";
  const [internalLinks, setInternalLinks] = useState(initialData?.internal_links?.join(", ") || "");

  const [useRichEditor, setUseRichEditor] = useState(true);
  const [previewMode, setPreviewMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [availableDocs, setAvailableDocs] = useState<Array<{ slug: string; title: string }>>([]);

  useEffect(() => {
    // Load existing documents for link suggestions
    getDocuments()
      .then((docs) => setAvailableDocs(docs.map((d) => ({ slug: d.slug, title: d.title }))))
      .catch(() => {});
  }, []);

  // Dirty state warning on window unload
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  const handleTitleChange = (val: string) => {
    setTitle(val);
    setIsDirty(true);
    if (isNew && (!slug || slug === generateSlug(title))) {
      setSlug(generateSlug(val));
    }
  };

  const generateSlug = (text: string) => {
    return text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  };

  // FAQ Management
  const handleAddFaq = () => {
    const newFaq: FAQItem = {
      id: `faq-${Date.now()}`,
      question: "",
      answer: "",
    };
    setFaqs([...faqs, newFaq]);
    setCollapsedFaqs((prev) => ({ ...prev, [newFaq.id]: false }));
    setIsDirty(true);
  };

  const toggleCollapseFaq = (id: string) => {
    setCollapsedFaqs((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleUpdateFaq = (index: number, field: "question" | "answer", val: string) => {
    const updated = [...faqs];
    updated[index] = { ...updated[index], [field]: val };
    setFaqs(updated);
    setIsDirty(true);
  };

  const handleRemoveFaq = (index: number) => {
    setFaqs(faqs.filter((_, i) => i !== index));
    setIsDirty(true);
  };

  const handleMoveFaq = (index: number, direction: "up" | "down") => {
    if (direction === "up" && index === 0) return;
    if (direction === "down" && index === faqs.length - 1) return;
    const targetIdx = direction === "up" ? index - 1 : index + 1;
    const updated = [...faqs];
    const temp = updated[index];
    updated[index] = updated[targetIdx];
    updated[targetIdx] = temp;
    setFaqs(updated);
    setIsDirty(true);
  };

  const handleSubmit = async (publishAndIndex: boolean = false) => {
    if (!title.trim()) {
      setMessage({ text: "Document title is required.", type: "error" });
      return;
    }
    if (!slug.trim()) {
      setMessage({ text: "Document slug is required.", type: "error" });
      return;
    }

    setSaving(true);
    setMessage(null);

    const validFaqs = faqs.filter(
      (f) => f.question.trim().length > 0 && f.answer.trim().length > 0
    );

    const docPayload: Partial<DocumentData> = {
      id: initialData?.id || slug.trim(),
      slug: slug.trim(),
      title: title.trim(),
      meta_description: metaDescription.trim(),
      content: content,
      content_schema_version: 2,
      structured_content: structuredContent,
      faqs: validFaqs,
      keywords: keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean),
      headings: headings
        .split(",")
        .map((h) => h.trim())
        .filter(Boolean),
      internal_links: internalLinks
        .split(",")
        .map((l) => l.trim())
        .filter(Boolean),
      status: publishAndIndex ? "published" : "draft",
      source_type: initialData?.source_type || "authored",
      created_at: initialData?.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    try {
      await saveDocument(docPayload);
      setIsDirty(false);
      setMessage({
        text: publishAndIndex
          ? "Document published and indexed into hybrid search engine!"
          : "Document saved successfully.",
        type: "success",
      });

      setTimeout(() => {
        router.push("/admin");
      }, 1000);
    } catch (err: unknown) {
      setMessage({ text: err instanceof Error ? err.message : "Failed to save document", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Top Breadcrumb & Actions */}
      <div className="flex items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-800">
        <Link
          href="/admin"
          onClick={(e) => {
            if (isDirty && !window.confirm("You have unsaved changes. Discard them?")) {
              e.preventDefault();
            }
          }}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors font-mono"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Notes</span>
        </Link>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPreviewMode(!previewMode)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-xs font-medium text-slate-300 transition-colors"
          >
            {previewMode ? <Edit3 className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            <span>{previewMode ? "Edit Mode" : "Preview"}</span>
          </button>

          <button
            type="button"
            onClick={() => handleSubmit(false)}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 hover:bg-slate-800 text-xs font-medium text-slate-200 transition-colors disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Draft</span>
          </button>

          <button
            type="button"
            onClick={() => handleSubmit(true)}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-semibold text-white shadow-sm transition-colors disabled:opacity-50"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Publish & Index</span>
          </button>
        </div>
      </div>

      {/* Status Message */}
      {message && (
        <div
          className={`mb-6 p-3 rounded-lg text-xs flex items-center gap-2 ${
            message.type === "success"
              ? "bg-emerald-950/40 border border-emerald-800 text-emerald-200"
              : "bg-rose-950/40 border border-rose-800 text-rose-200"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {previewMode ? (
        <div className="bg-slate-900/90 p-8 rounded-xl border border-slate-800 shadow-sm space-y-6">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-100 mb-2">{title || "Untitled Note"}</h1>
            {metaDescription && <p className="text-slate-400 italic">{metaDescription}</p>}
          </div>

          <div className="border-t border-slate-800 pt-6">
            <MarkdownRenderer content={content} />
          </div>

          {faqs.length > 0 && (
            <div className="border-t border-slate-800 pt-6">
              <h3 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-sky-400" />
                <span>Frequently Asked Questions ({faqs.length})</span>
              </h3>
              <div className="space-y-3">
                {faqs.map((faq) => (
                  <div key={faq.id} className="bg-slate-950/80 border border-slate-800 rounded-lg p-4">
                    <h4 className="font-semibold text-sm text-slate-200 mb-1">{faq.question}</h4>
                    <p className="text-xs text-slate-400 leading-relaxed">{faq.answer}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); handleSubmit(true); }} className="space-y-6">
          {/* Title & Slug */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2 space-y-1">
              <label className="text-xs font-semibold text-slate-300">
                Document Title *
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => handleTitleChange(e.target.value)}
                placeholder="e.g. My Bicycle Maintenance Journey"
                required
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-medium"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-300">
                Slug (URL Identifier) *
              </label>
              <input
                type="text"
                value={slug}
                onChange={(e) => { setSlug(e.target.value); setIsDirty(true); }}
                placeholder="my-bicycle-maintenance"
                required
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono"
              />
            </div>
          </div>

          {/* Meta Description */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-300">
              Meta Description (Used for SERP snippet fallback & lexical indexing)
            </label>
            <textarea
              value={metaDescription}
              onChange={(e) => { setMetaDescription(e.target.value); setIsDirty(true); }}
              rows={2}
              placeholder="Concise summary of this knowledge document..."
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
            />
          </div>

          {/* Structured Document Body Editor */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-2">
                <span>Document Content</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800">
                  Schema v2: JSON AST + Markdown
                </span>
              </label>
              <div className="flex items-center gap-3">
                <span className="text-[11px] text-slate-500 font-mono">
                  {content.split(/\s+/).filter(Boolean).length} words
                </span>
                <button
                  type="button"
                  onClick={() => setUseRichEditor(!useRichEditor)}
                  className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1 font-mono"
                >
                  <Code2 className="w-3.5 h-3.5" />
                  <span>{useRichEditor ? "Raw Markdown" : "Rich Editor"}</span>
                </button>
              </div>
            </div>

            {useRichEditor ? (
              <StructuredEditor
                initialContent={content}
                initialStructuredContent={structuredContent}
                availableSlugs={availableDocs}
                onChange={(ast, markdown) => {
                  setStructuredContent(ast);
                  setContent(markdown);
                  setIsDirty(true);
                }}
              />
            ) : (
              <textarea
                value={content}
                onChange={(e) => {
                  setContent(e.target.value);
                  setIsDirty(true);
                }}
                rows={16}
                placeholder="Write document content with markdown headings (#, ##), paragraphs, and internal links [Label](/doc/slug)..."
                required
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-sm text-slate-100 font-mono leading-relaxed placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
            )}
          </div>

          {/* Native FAQ Schema Section */}
          <div className="border border-slate-800 bg-slate-900/60 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  <HelpCircle className="w-4 h-4 text-sky-400" />
                  <span>PESE-Native FAQ Schema ({faqs.length})</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  First-class Q&A knowledge pairs directly indexed into passage retrieval, featured answers, and PAA.
                </p>
              </div>
              <button
                type="button"
                onClick={handleAddFaq}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600/20 border border-sky-500/30 hover:bg-sky-600/30 text-sky-400 text-xs font-semibold transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add FAQ</span>
              </button>
            </div>

            {faqs.length === 0 ? (
              <div className="text-center py-6 border border-dashed border-slate-800 rounded-lg text-slate-500 text-xs">
                No FAQ entries added yet. Click &quot;Add FAQ&quot; to build direct answer candidates.
              </div>
            ) : (
              <div className="space-y-4">
                {faqs.map((faq, index) => {
                  const isCollapsed = collapsedFaqs[faq.id] ?? false;
                  return (
                    <div
                      key={faq.id}
                      className="bg-slate-950/90 border border-slate-800 rounded-xl p-4 space-y-3 relative transition-all"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <button
                          type="button"
                          onClick={() => toggleCollapseFaq(faq.id)}
                          className="flex items-center gap-2 text-left flex-1 hover:text-sky-300 transition-colors"
                        >
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-sky-400 font-bold">
                            FAQ #{index + 1}
                          </span>
                          <span className="text-xs font-semibold text-slate-200 truncate max-w-md">
                            {faq.question.trim() || <span className="italic text-slate-500 font-normal">Untitled Question</span>}
                          </span>
                        </button>
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => toggleCollapseFaq(faq.id)}
                            className="p-1 rounded hover:bg-slate-800 text-slate-400 transition-colors"
                            title={isCollapsed ? "Expand FAQ" : "Collapse FAQ"}
                          >
                            <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${isCollapsed ? "-rotate-90" : ""}`} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleMoveFaq(index, "up")}
                            disabled={index === 0}
                            className="p-1 rounded hover:bg-slate-800 text-slate-400 disabled:opacity-20"
                            title="Move up (Alt+Up)"
                            aria-label={`Move FAQ #${index + 1} up`}
                          >
                            <ChevronUp className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleMoveFaq(index, "down")}
                            disabled={index === faqs.length - 1}
                            className="p-1 rounded hover:bg-slate-800 text-slate-400 disabled:opacity-20"
                            title="Move down (Alt+Down)"
                            aria-label={`Move FAQ #${index + 1} down`}
                          >
                            <ChevronDown className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemoveFaq(index)}
                            className="p-1 rounded hover:bg-rose-950/60 text-rose-400 transition-colors ml-1"
                            title="Delete FAQ"
                            aria-label={`Delete FAQ #${index + 1}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {!isCollapsed && (
                        <div className="space-y-3 pt-2 border-t border-slate-900">
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium">
                              <span>Question</span>
                              <span className="text-[10px] font-mono text-slate-500">{faq.question.length} chars</span>
                            </div>
                            <input
                              type="text"
                              value={faq.question}
                              onChange={(e) => handleUpdateFaq(index, "question", e.target.value)}
                              placeholder="e.g. How often should I lubricate the bicycle chain?"
                              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 font-medium"
                            />
                          </div>

                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium">
                              <span>Answer</span>
                              <span className="text-[10px] font-mono text-slate-500">{faq.answer.length} chars</span>
                            </div>
                            <textarea
                              value={faq.answer}
                              onChange={(e) => handleUpdateFaq(index, "answer", e.target.value)}
                              rows={3}
                              placeholder="Clean the chain and apply lubricant every 100-150 miles or after riding in heavy rain."
                              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 leading-relaxed"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Keywords & Internal Links */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-300">
                Keywords / Tags (Comma-separated)
              </label>
              <input
                type="text"
                value={keywords}
                onChange={(e) => { setKeywords(e.target.value); setIsDirty(true); }}
                placeholder="bicycle, maintenance, chain, 2024"
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-300">
                Internal Document Links (Target slugs, comma-separated)
              </label>
              <input
                type="text"
                value={internalLinks}
                onChange={(e) => { setInternalLinks(e.target.value); setIsDirty(true); }}
                placeholder="my-first-bicycle, things-i-bought-in-2024"
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono"
              />
            </div>
          </div>

          {/* Status & Guard Notice */}
          <div className="pt-4 border-t border-slate-800 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <label className="text-xs font-semibold text-slate-300">Status:</label>
              <span className="text-xs text-slate-400">Save Draft removes this page from search. Publish &amp; Index makes it searchable.</span>
            </div>

            <div className="text-[11px] text-slate-500 font-mono italic">
              🔒 PESE Integrity: Structured AST & FAQs are indexed directly into passage vectors and BM25F without ranking multiplier inflation.
            </div>
          </div>
        </form>
      )}
    </div>
  );
};
