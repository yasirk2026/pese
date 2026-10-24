"use client";

import React, { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { DocumentEditorForm } from "@/components/DocumentEditorForm";
import { getDocumentBySlug, DocumentData } from "@/lib/api";
import { ArrowLeft, AlertCircle, Loader2 } from "lucide-react";

function EditNoteContent() {
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
        <div className="max-w-4xl mx-auto py-20 flex flex-col items-center justify-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
          <p className="text-sm font-mono text-neutral-500">Loading note editor...</p>
        </div>
      </AppShell>
    );
  }

  if (error || !doc) {
    return (
      <AppShell>
        <div className="max-w-4xl mx-auto py-16 flex flex-col items-center justify-center text-center">
          <div className="w-12 h-12 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex items-center justify-center mb-4">
            <AlertCircle className="w-6 h-6 text-rose-500" />
          </div>
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100 mb-2">Note Not Found</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6 font-mono">
            {slug ? `The note '${slug}' could not be loaded.` : "No note slug was specified."}
          </p>
          <Link
            href="/admin"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to Notes</span>
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <DocumentEditorForm initialData={doc} isNew={false} />
    </AppShell>
  );
}

export default function EditDocumentPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <div className="max-w-4xl mx-auto py-20 flex flex-col items-center justify-center">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
            <p className="text-sm font-mono text-neutral-500">Loading note editor...</p>
          </div>
        </AppShell>
      }
    >
      <EditNoteContent />
    </Suspense>
  );
}
