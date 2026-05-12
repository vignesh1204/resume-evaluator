import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

// Google "G" logo in brand colours
function GoogleIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

function Avatar({ user }) {
  const src = user?.user_metadata?.avatar_url;
  const name =
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email?.split("@")[0] ||
    "User";

  if (src) {
    return (
      <img
        src={src}
        alt={name}
        className="h-8 w-8 rounded-full object-cover ring-1 ring-white/20"
      />
    );
  }

  // Fallback: initials
  return (
    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-600/70 text-xs font-semibold uppercase ring-1 ring-white/20">
      {name.charAt(0)}
    </div>
  );
}

export default function Header() {
  const { user, loading, signInWithGoogle, signOut } = useAuth();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const displayName =
    user?.user_metadata?.full_name ||
    user?.user_metadata?.name ||
    user?.email?.split("@")[0] ||
    "User";

  const firstName = displayName.split(" ")[0];

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#07080d]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        {/* Logo */}
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2.5 transition-opacity hover:opacity-80"
        >
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-violet-500 to-cyan-400">
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M9 12l2 2 4-4M7 2h10a2 2 0 012 2v16a2 2 0 01-2 2H7a2 2 0 01-2-2V4a2 2 0 012-2z"
                stroke="white"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <span className="text-sm font-semibold tracking-tight text-white/90">
            Resume Eval
          </span>
        </button>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {loading ? (
            // Skeleton while session hydrates
            <div className="h-8 w-28 animate-pulse rounded-xl bg-white/5" />
          ) : user ? (
            // Signed-in: avatar + dropdown
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setDropdownOpen((o) => !o)}
                className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm transition-colors hover:bg-white/10"
              >
                <Avatar user={user} />
                <span className="max-w-[96px] truncate font-medium text-white/90">
                  {firstName}
                </span>
                <svg
                  className={`h-3.5 w-3.5 text-white/40 transition-transform ${
                    dropdownOpen ? "rotate-180" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="2.5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {/* Dropdown menu */}
              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 origin-top-right rounded-2xl border border-white/10 bg-[#0e1020]/95 p-1 shadow-[0_20px_60px_rgba(0,0,0,0.5)] backdrop-blur-xl">
                  <div className="px-3 py-2.5">
                    <p className="truncate text-sm font-medium text-white/90">
                      {displayName}
                    </p>
                    <p className="truncate text-xs text-white/40 mt-0.5">
                      {user.email}
                    </p>
                  </div>
                  <div className="my-1 border-t border-white/8" />
                  <button
                    onClick={async () => {
                      setDropdownOpen(false);
                      await signOut();
                      navigate("/");
                    }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/8 hover:text-white/90"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                      />
                    </svg>
                    Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            // Signed-out: Google sign-in button
            <button
              onClick={signInWithGoogle}
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3.5 py-2 text-sm font-medium text-white/80 transition-all hover:bg-white/10 hover:text-white active:scale-[0.98]"
            >
              <GoogleIcon size={16} />
              Sign in with Google
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
