import type { BetaStatus } from "@/lib/api";

export function BetaDisclosure({agreement}: {agreement?: BetaStatus["agreement"]}) {
  return <aside className="rounded-xl border-2 border-orange-500/70 bg-orange-500/5 p-5 space-y-3" aria-label="Experimental learning privacy warning" data-testid="beta-privacy-warning">
    <h3 className="font-bold text-orange-600">PESE NEURAL GENESIS: AGGRESSIVE LEARNING BETA</h3>
    <p className="font-semibold">Do not add highly personal journals, passwords, financial records, private correspondence, confidential documents, medical records or other sensitive material to the BETA learning scope.</p>
    <p className="text-sm">Use educational notes, study materials, public research and technical documentation. Approved materials, searches and feedback may be processed locally for future experimental models. Local processing does not make sensitive content risk-free.</p>
    <p className="text-sm">Training can retain patterns. Removing documents, deleting examples or reaching the retention period does not guarantee selective erasure of learned influence. No data is automatically transmitted to Maniac Softwares; external sharing requires separate explicit authorization.</p>
    {agreement&&<details><summary className="cursor-pointer font-medium text-sm">Read the full training/privacy agreement</summary><ul className="list-disc pl-5 space-y-2 text-sm mt-3">{agreement.statements.map(s=><li key={s}>{s}</li>)}</ul></details>}
  </aside>;
}
