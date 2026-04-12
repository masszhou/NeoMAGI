import { useEffect } from "react"
import { ChatPage } from "@/components/chat/ChatPage"
import { LoginForm } from "@/components/LoginForm"
import { useAuthStore } from "@/stores/auth"

function App() {
  const { authRequired, token, checkAuthStatus } = useAuthStore()

  useEffect(() => {
    checkAuthStatus()
  }, [checkAuthStatus])

  // Still checking auth status
  if (authRequired === null) {
    return null
  }

  // Auth required but no token → show login
  if (authRequired && !token) {
    return <LoginForm />
  }

  // No auth required, or have token → show chat
  return <ChatPage />
}

export default App
