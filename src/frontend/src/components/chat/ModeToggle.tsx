import type { SessionMode } from "@/stores/chat"

interface ModeToggleProps {
  mode: SessionMode
  onToggle: (mode: SessionMode) => void
  sessionId: string
}

export function ModeToggle({ mode, onToggle }: ModeToggleProps) {
  const isCoding = mode === "coding"
  const next: SessionMode = isCoding ? "chat_safe" : "coding"

  return (
    <button
      onClick={() => onToggle(next)}
      className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
        isCoding
          ? "bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-300"
          : "bg-muted text-muted-foreground hover:bg-accent"
      }`}
      title={isCoding ? "Switch to chat_safe mode" : "Switch to coding mode"}
    >
      {isCoding ? "coding" : "chat_safe"}
    </button>
  )
}
