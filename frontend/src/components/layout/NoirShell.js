import React from "react";

export default function NoirShell({ children, className = "" }) {
  return (
    <div className={`min-h-screen w-full noir-bg ${className}`}>
      <div className="noir-grain min-h-screen w-full">{children}</div>
    </div>
  );
}