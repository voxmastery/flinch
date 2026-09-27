interface InlineCodeProps {
  text: string;
}

/** Renders `backticked` spans of a real Flinch message as <code>. */
export function InlineCode({ text }: InlineCodeProps) {
  const parts = text.split("`");
  return <>{parts.map((part, i) => (i % 2 === 1 ? <code key={i}>{part}</code> : <span key={i}>{part}</span>))}</>;
}
