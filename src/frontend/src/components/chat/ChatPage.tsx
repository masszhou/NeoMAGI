import { useEffect } from "react"
import { useChatStore } from "@/stores/chat"
import type { SessionMode } from "@/stores/chat"
import { Toaster } from "@/components/ui/sonner"
import { ConnectionStatus } from "./ConnectionStatus"
import { MessageList } from "./MessageList"
import { MessageInput } from "./MessageInput"
import { ThreadRail } from "./ThreadRail"
import { ModeToggle } from "./ModeToggle"

const WS_URL = "ws://localhost:19789/ws"

export function ChatPage() {
  const connect = useChatStore((state) => state.connect)
  const disconnect = useChatStore((state) => state.disconnect)
  const activeSessionId = useChatStore((state) => state.activeSessionId)
  const mode = useChatStore(
    (state) => state.sessionsById[state.activeSessionId]?.mode ?? "chat_safe",
  ) as SessionMode
  const setMode = useChatStore((state) => state.setMode)

  useEffect(() => {
    connect(WS_URL)
    return () => disconnect()
  }, [connect, disconnect])

  return (
    <div className="flex h-screen bg-background">
      <ThreadRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h1 className="text-lg font-semibold">NeoMAGI</h1>
          <ModeToggle mode={mode} onToggle={setMode} sessionId={activeSessionId} />
        </header>
        <ConnectionStatus />
        <MessageList />
        <MessageInput />
      </div>
      <Toaster position="top-right" richColors closeButton />
    </div>
  )
}
