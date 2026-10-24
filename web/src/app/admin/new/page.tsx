"use client";

import React from "react";
import { AppShell } from "@/components/AppShell";
import { DocumentEditorForm } from "@/components/DocumentEditorForm";

export default function NewNotePage() {
  return (
    <AppShell>
      <DocumentEditorForm isNew={true} />
    </AppShell>
  );
}
