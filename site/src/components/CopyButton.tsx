import { useEffect, useState } from "react";

interface CopyButtonProps {
  text: string;
  label: string;
}

async function writeClipboard(text: string): Promise<boolean> {
  try {
    const timeout = new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error("timeout")), 800));
    await Promise.race([navigator.clipboard.writeText(text), timeout]);
    return true;
  } catch {
    // Fallback for browsers without the async clipboard API (or without permission).
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  }
}

export function CopyButton({ text, label }: CopyButtonProps) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (status === "idle") return;
    const id = window.setTimeout(() => setStatus("idle"), 2000);
    return () => window.clearTimeout(id);
  }, [status]);

  const copy = async () => setStatus((await writeClipboard(text)) ? "copied" : "failed");

  return (
    <button type="button" className={`copy-btn is-${status}`} onClick={copy} aria-label={status === "idle" ? label : undefined}>
      <span aria-live="polite">{status === "copied" ? "Copied" : status === "failed" ? "Copy failed" : "Copy"}</span>
    </button>
  );
}
