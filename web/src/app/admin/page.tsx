"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import {
  getDocuments,
  deleteDocument,
  reindexAll,
  DocumentData,
} from "@/lib/api";
import {
  Plus,
  RefreshCw,
  Trash2,
  Edit,
  ExternalLink,
  Search,
  FileText,
  Tag,
  Link2,
} from "lucide-react";

export default function NotesPage() {
  const [documents, setDocuments] = useState<DocumentData[]>([]);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const [filterQuery, setFilterQuery] = useState("");

  const loadDocs = () => {
    setLoading(true);
    getDocuments()
      .then((data) => {
        setDocuments(data);
        setLoading(false);
      })
      .catch((err) => {
        setNotification(`Error loading notes: ${err instanceof Error ? err.message : "Request failed"}`);
        setLoading(false);
      });
  };

  useEffect(() => {
    let active = true;
    getDocuments()
      .then((data) => {
        if (active) {
          setDocuments(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setNotification(String(err));
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const handleReindex = async () => {
    setReindexing(true);
    try {
      const res = await reindexAll();
      setNotification(`Reindexed ${res.documents_indexed} notes and ${res.passages_indexed} passages in ${res.took_ms} ms`);
      loadDocs();
    } catch (err: unknown) {
      setNotification(`Reindex failed: ${err instanceof Error ? err.message : "Request failed"}`);
    } finally {
      setReindexing(false);
    }
  };

  const handleDelete = async (slug: string, title: string) => {
    if (!confirm(`Are you sure you want to delete note "${title}"?`)) {
      return;
    }
    try {
      await deleteDocument(slug);
      setNotification(`Deleted note "${title}"`);
      loadDocs();
    } catch (err: unknown) {
      setNotification(`Delete failed: ${err instanceof Error ? err.message : "Request failed"}`);
    }
  };

  const filteredDocs = documents.filter(
    (d) =>
      d.title.toLowerCase().includes(filterQuery.toLowerCase()) ||
      d.slug.toLowerCase().includes(filterQuery.toLowerCase()) ||
      d.keywords.some((k) => k.toLowerCase().includes(filterQuery.toLowerCase()))
  );

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header & Main Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-surface-border">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border border-blue-200/50 dark:border-blue-800/50">
                <FileText className="w-5 h-5" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50">
                Notes
              </h1>
            </div>
            <p className="mt-1.5 text-sm text-neutral-500 dark:text-neutral-400">
              Personal knowledge and structured notes stored privately inside your PESE Brain.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={handleReindex}
              disabled={reindexing}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white dark:bg-neutral-900 text-xs font-medium text-neutral-700 dark:text-neutral-300 border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50 cursor-pointer shadow-2xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${reindexing ? "animate-spin" : ""}`} />
              <span>{reindexing ? "Reindexing..." : "Reindex All"}</span>
            </button>

            <Link
              href="/admin/new"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-xs font-medium text-white shadow-xs transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>New Note</span>
            </Link>
          </div>
        </div>

        {/* Notification Banner */}
        {notification && (
          <div className="p-3.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/80 rounded-xl text-blue-900 dark:text-blue-200 text-xs flex items-center justify-between shadow-2xs">
            <span>{notification}</span>
            <button
              type="button"
              onClick={() => setNotification(null)}
              className="text-blue-600 dark:text-blue-400 font-bold ml-4 cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}

        {/* Filter Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="relative w-full max-w-md">
            <Search className="w-4 h-4 text-neutral-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="Filter notes by title, slug, or keywords..."
              className="w-full bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-xl pl-9 pr-3.5 py-2 text-xs text-neutral-900 dark:text-neutral-100 placeholder-neutral-400 dark:placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all shadow-2xs"
            />
          </div>
          <span className="text-xs text-neutral-500 font-mono text-right">
            {filteredDocs.length} of {documents.length} notes
          </span>
        </div>

        {/* Notes Table */}
        <div className="bg-white dark:bg-neutral-900/90 rounded-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden shadow-xs">
          {loading ? (
            <div className="py-16 text-center text-sm text-neutral-500">Loading notes...</div>
          ) : filteredDocs.length === 0 ? (
            <div className="py-16 text-center text-sm text-neutral-500">No notes found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-neutral-50/80 dark:bg-neutral-850/60 text-neutral-500 dark:text-neutral-400 font-mono uppercase text-[10px] tracking-wider border-b border-neutral-200 dark:border-neutral-800">
                  <tr>
                    <th className="px-5 py-3.5">Note Title</th>
                    <th className="px-5 py-3.5">Status</th>
                    <th className="px-5 py-3.5">Keywords</th>
                    <th className="px-5 py-3.5">Internal Links</th>
                    <th className="px-5 py-3.5">Updated</th>
                    <th className="px-5 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/80">
                  {filteredDocs.map((doc) => (
                    <tr
                      key={doc.id}
                      className="hover:bg-neutral-50/70 dark:hover:bg-neutral-800/40 transition-colors"
                    >
                      <td className="px-5 py-3.5">
                        <Link
                          href={`/doc?slug=${encodeURIComponent(doc.slug)}`}
                          className="font-medium text-neutral-900 dark:text-neutral-100 hover:text-blue-600 dark:hover:text-blue-400 flex items-center gap-1.5 transition-colors"
                        >
                          <span>{doc.title}</span>
                          <ExternalLink className="w-3 h-3 text-neutral-400 opacity-60" />
                        </Link>
                        <div className="text-[11px] font-mono text-neutral-400 mt-0.5">
                          note://{doc.slug}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-medium ${
                            doc.status === "published"
                              ? "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-800/60"
                              : "bg-neutral-200 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-400"
                          }`}
                        >
                          {doc.status}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {doc.keywords.slice(0, 3).map((kw) => (
                            <span
                              key={kw}
                              className="px-2 py-0.5 rounded-md bg-neutral-100 dark:bg-neutral-800 text-[10px] font-mono text-neutral-600 dark:text-neutral-400"
                            >
                              {kw}
                            </span>
                          ))}
                          {doc.keywords.length > 3 && (
                            <span className="text-[10px] text-neutral-400">
                              +{doc.keywords.length - 3}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 font-mono text-neutral-500">
                        {doc.internal_links.length} links
                      </td>
                      <td className="px-5 py-3.5 text-neutral-500 font-mono text-[11px]">
                        {new Date(doc.updated_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            href={`/admin/edit?slug=${encodeURIComponent(doc.slug)}`}
                            className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                            title="Edit Note"
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </Link>
                          <button
                            type="button"
                            onClick={() => handleDelete(doc.id, doc.title)}
                            className="p-1.5 rounded-lg text-neutral-500 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
                            title="Delete Note"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
