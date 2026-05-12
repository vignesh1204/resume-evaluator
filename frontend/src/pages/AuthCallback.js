import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../utils/supabase";

export default function AuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    // Supabase automatically exchanges the code from the URL.
    // Waiting for a settled session is enough before redirecting.
    supabase.auth.getSession().then(({ data: { session } }) => {
      navigate(session ? "/app" : "/", { replace: true });
    });
  }, [navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center noir-bg">
      <div className="flex flex-col items-center gap-4">
        <svg
          className="h-8 w-8 animate-spin text-white/40"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <p className="text-sm noir-muted">Signing you in…</p>
      </div>
    </div>
  );
}
