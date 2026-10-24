"use client";

import React, { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { MarkdownRenderer } from "@/lib/markdown";
import { getDocumentBySlug, DocumentData } from "@/lib/api";
import {
  ArrowLeft,
  Calendar,
  Tag,
  Link2,
  HelpCircle,
  ChevronDown,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Edit,
} from "lucide-react";

function DocumentViewContent() {
  const searchParams = useSearchParams();
  const slug = searchParams.get("slug") || "";

  const [doc, setDoc] = useState<DocumentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug.trim()) {
      setLoading(false);
      setError("No note slug specified.");
      return;
    }

    setLoading(true);
    setError(null);

    getDocumentBySlug(slug)
      .then((data) => {
        setDoc(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Note not found");
        setLoading(false);
      });
  }, [slug]);

  if (loading) {
    return (
      <AppShell>
        <div className="max-w-3xl mx-auto py-24 flex flex-col items-center justify-center text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
          <p className="text-sm font-mono text-neutral-500">Loading note...</p>
        </div>
      </AppShell>
    );
  }

  if (error || !doc) {
    return (
      <AppShell>
        <div className="max-w-3xl mx-auto py-20 flex flex-col items-center justify-center text-center">
          <div className="w-12 h-12 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex items-center justify-center mb-4">
            <AlertCircle className="w-6 h-6 text-rose-500" />
          </div>
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100 mb-2">Note Not Found</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6 font-mono">
            {slug ? `The note '${slug}' could not be located.` : "No note slug was specified."}
          </p>
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 text-xs font-mono text-neutral-700 dark:text-neutral-300 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Return to Search</span>
            </Link>
            <Link
              href="/admin"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-xs font-mono text-white transition-colors"
            >
              <span>Open Notes</span>
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const createdDate = new Date(doc.created_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const updatedDate = new Date(doc.updated_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto">
        {/* Navigation Breadcrumb */}
        <div className="mb-6 flex items-center justify-between text-xs text-neutral-500 font-mono">
          <Link
            href="/admin"
            className="flex items-center gap-1.5 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Notes</span>
          </Link>
          <div className="flex items-center gap-2">
            <span className="bg-neutral-100 dark:bg-neutral-900 px-2 py-0.5 rounded-md border border-neutral-200 dark:border-neutral-800">
              note://{doc.slug}
            </span>
            <Link
              href={`/admin/edit?slug=${encodeURIComponent(doc.slug)}`}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border border-blue-200/60 dark:border-blue-800/60 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
            >
              <Edit className="w-3 h-3" />
              <span>Edit</span>
            </Link>
          </div>
        </div>

        {/* Note Header */}
        <header className="mb-8 pb-6 border-b border-surface-border">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50 font-sans leading-tight">
            {doc.title}
          </h1>

          {doc.meta_description && (
            <p className="mt-3 text-base text-neutral-600 dark:text-neutral-400 italic leading-relaxed">
              {doc.meta_description}
            </p>
          )}

          {/* Metadata Row */}
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-neutral-500 font-mono">
            <span className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-neutral-400" />
              Published: {createdDate}
            </span>
            {createdDate !== updatedDate && (
              <span>• Updated: {updatedDate}</span>
            )}
            {doc.link_details && (
              <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                <Link2 className="w-3.5 h-3.5" />
                {doc.link_details.in_degree} internal backlinks
              </span>
            )}
          </div>

          {/* Tags */}
          {doc.keywords && doc.keywords.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <Tag className="w-3 h-3 text-neutral-400 mr-1" />
              {doc.keywords.map((kw) => (
                <Link
                  key={kw}
                  href={`/search?q=${encodeURIComponent(kw)}`}
                  className="px-2.5 py-0.5 rounded-full bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 text-[11px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 transition-colors"
                >
                  #{kw}
                </Link>
              ))}
            </div>
          )}
        </header>

        {/* Markdown Note Content */}
        <article className="prose prose-neutral dark:prose-invert max-w-none leading-relaxed text-neutral-800 dark:text-neutral-200">
          <MarkdownRenderer content={doc.content} />
        </article>

        {/* Native FAQ Accordion Section */}
        {doc.faqs && doc.faqs.length > 0 && (
          <section className="mt-12 pt-8 border-t border-surface-border">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-blue-500" />
                <span>Frequently Asked Questions</span>
              </h2>
              <span className="text-xs font-mono px-2 py-0.5 rounded-md bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-neutral-500">
                {doc.faqs.length} {doc.faqs.length === 1 ? "entry" : "entries"}
              </span>
            </div>

            <div className="space-y-3">
              {doc.faqs.map((faq, idx) => (
                <details
                  key={faq.id || idx}
                  className="group bg-white dark:bg-neutral-900/60 border border-neutral-200 dark:border-neutral-800 rounded-xl overflow-hidden transition-colors"
                  open={idx === 0}
                >
                  <summary className="flex items-center justify-between px-5 py-3.5 cursor-pointer select-none font-medium text-neutral-900 dark:text-neutral-200 text-sm hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
                    <span className="flex items-center gap-2.5">
                      <span className="text-xs font-mono text-blue-600 dark:text-blue-400 font-bold">
                        Q{idx + 1}.
                      </span>
                      <span>{faq.question}</span>
                    </span>
                    <ChevronDown className="w-4 h-4 text-neutral-400 group-open:rotate-180 transition-transform duration-200 shrink-0 ml-2" />
                  </summary>
                  <div className="px-5 pb-5 pt-1 text-neutral-700 dark:text-neutral-300 text-sm leading-relaxed border-t border-neutral-100 dark:border-neutral-800/60">
                    <p>{faq.answer}</p>
                    <div className="mt-3 flex items-center gap-1.5 text-[11px] font-mono text-neutral-500">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                      <span>Verified author-crafted answer candidate</span>
                    </div>
                  </div>
                </details>
              ))}
            </div>
          </section>
        )}

        {/* Knowledge Graph Backlinks Footer */}
        {doc.link_details && doc.link_details.in_links.length > 0 && (
          <aside className="mt-12 pt-6 border-t border-surface-border">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 font-mono uppercase tracking-wider flex items-center gap-1.5">
              <Link2 className="w-4 h-4 text-blue-500" />
              Notes Linking Here ({doc.link_details.in_links.length})
            </h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {doc.link_details.in_links.map((srcSlug) => (
                <Link
                  key={srcSlug}
                  href={`/doc?slug=${encodeURIComponent(srcSlug)}`}
                  className="px-3 py-1.5 rounded-lg bg-white dark:bg-neutral-900 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-xs text-blue-600 dark:text-blue-400 border border-neutral-200 dark:border-neutral-800 font-mono transition-colors shadow-2xs"
                >
                  note://{srcSlug}
                </Link>
              ))}
            </div>
          </aside>
        )}
      </div>
    </AppShell>
  );
}

export default function DocumentPage() {
  return (
    <Suspense
      fallback={
        <div className="p-12 text-center text-sm text-neutral-500">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-4" />
          <p className="font-mono">Loading note...</p>
        </div>
      }
    >
      <DocumentViewContent />
    </Suspense>
  );
}
