import { ShieldCheck } from "lucide-react";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-jade-900 text-cream-50 shadow-sm ring-1 ring-jade-900/10">
        <ShieldCheck size={18} strokeWidth={2} aria-hidden="true" />
      </span>
      {!compact && (
        <span className="font-display text-[1.35rem] font-semibold tracking-[-0.025em] text-ink-950">
          Insure<span className="text-jade-700">Tutor</span>
        </span>
      )}
    </div>
  );
}

