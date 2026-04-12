import { useState } from "react"
import { useAuthStore } from "@/stores/auth"

export function LoginForm() {
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const { login, loading } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const result = await login(password)
    if (!result.ok) {
      setError(
        result.error === "AUTH_RATE_LIMITED"
          ? "Too many attempts. Please wait."
          : "Invalid password."
      )
      setPassword("")
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 p-6 border rounded-lg"
      >
        <h2 className="text-lg font-semibold text-center">NeoMAGI</h2>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
          disabled={loading}
          className="w-full px-3 py-2 border rounded-md bg-background text-foreground"
        />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button
          type="submit"
          disabled={loading || !password}
          className="w-full px-3 py-2 bg-primary text-primary-foreground rounded-md disabled:opacity-50"
        >
          {loading ? "..." : "Login"}
        </button>
      </form>
    </div>
  )
}
