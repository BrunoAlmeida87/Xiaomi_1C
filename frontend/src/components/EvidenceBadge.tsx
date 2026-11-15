import type { Evidence } from "../types";

const LABEL: Record<Evidence, string> = {
  verified: "Comprovado",
  documented_model: "Documentado (1C)",
  documented_related: "Modelos relacionados",
  experimental: "Experimental",
  not_implemented: "Não suportado",
};

export function EvidenceBadge({ e }: { e: Evidence }) {
  return <span className={`badge ev-${e}`}>{LABEL[e]}</span>;
}
