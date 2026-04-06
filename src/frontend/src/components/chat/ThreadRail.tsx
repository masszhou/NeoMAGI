import { useChatStore } from "@/stores/chat"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function ThreadRail() {
  const activeSessionId = useChatStore((s) => s.activeSessionId)
  const sessionOrder = useChatStore((s) => s.sessionOrder)
  const sessionsById = useChatStore((s) => s.sessionsById)
  const createThread = useChatStore((s) => s.createThread)
  const switchThread = useChatStore((s) => s.switchThread)

  return (
    <div className="flex w-64 shrink-0 flex-col border-r bg-muted/30">
      <div className="border-b p-3">
        <Button
          onClick={createThread}
          variant="outline"
          className="w-full"
          size="sm"
        >
          + New Thread
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {[...sessionOrder]
          .sort((a, b) => (sessionsById[b]?.lastActivityAt ?? 0) - (sessionsById[a]?.lastActivityAt ?? 0))
          .map((sessionId) => {
          const session = sessionsById[sessionId]
          if (!session) return null
          const isActive = sessionId === activeSessionId
          return (
            <button
              key={sessionId}
              onClick={() => switchThread(sessionId)}
              className={cn(
                "w-full border-b border-border/40 px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent",
                isActive && "bg-accent",
              )}
            >
              <div className="flex items-center gap-2">
                <span className="flex-1 truncate font-medium">
                  {session.title}
                </span>
                {session.isStreaming && (
                  <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-blue-500" />
                )}
                {!session.isStreaming && session.hasUnreadCompletion && (
                  <span className="h-2 w-2 shrink-0 rounded-full bg-green-500" />
                )}
              </div>
              <div className="mt-0.5 flex items-center gap-1">
                {session.lastAssistantPreview ? (
                  <p className="flex-1 truncate text-xs text-muted-foreground">
                    {session.lastAssistantPreview}
                  </p>
                ) : (
                  <p className="flex-1 text-xs text-muted-foreground/60">
                    {session.isStreaming ? "Running..." : "No messages"}
                  </p>
                )}
                <span className="shrink-0 text-[10px] text-muted-foreground/60">
                  {formatTime(session.lastActivityAt)}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
